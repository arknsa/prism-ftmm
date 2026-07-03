"""Admin user-provisioning service (P2.4).

Provides two operations:
  provision_user  — create Supabase Auth user + matching APP_USER row
  deactivate_user — set APP_USER.is_active=False + ban Supabase Auth user

Design constraints (D-043, D-031, D-036):
  - Supabase Auth is the authentication identity provider.
  - APP_USER is the authorization store; it is never deleted (audit integrity).
  - The Supabase Admin call happens first; the DB write is wrapped in a
    transaction. If the DB write fails after Supabase creation, the orphaned
    Supabase UUID is logged as a WARNING so an operator can clean up manually.
    This is an accepted MVP limitation: no distributed transaction.
  - write_audit_entry() is called inside the same session for every mutation;
    the caller owns the commit boundary.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from supabase import Client

from app.models.security import AppUser, Role
from app.services.audit import write_audit_entry

logger = logging.getLogger(__name__)

# ~100 years: effectively permanent ban duration for deactivated users (D-043).
_SUPABASE_BAN_DURATION_PERMANENT = "876600h"


def _get_role_by_name(role_name: str, session: Session) -> Role:
    """Return the Role row for role_name; raise HTTP 400 if unknown."""
    role = session.scalars(select(Role).where(Role.role_name == role_name)).first()
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown role '{role_name}'. "
                "Valid roles: Admin, Data Curator, Faculty Viewer, Read Only."
            ),
        )
    return role


def provision_user(
    *,
    email: str,
    password: str,
    role_name: str,
    session: Session,
    supabase: Client,
    actor_user_id: int,
) -> tuple[AppUser, str]:
    """Create a Supabase Auth user and the matching APP_USER row.

    Args:
        email: Email address for the new user.
        password: Initial password passed to Supabase Auth (never stored in DB).
        role_name: One of the four seeded role names.
        session: Active SQLAlchemy session; caller owns the commit.
        supabase: Authenticated Supabase client (service-role key).
        actor_user_id: user_id of the Admin performing the action (for audit).

    Returns:
        (app_user, role_name_str) — the unsaved AppUser instance plus the
        resolved role name, for use in the response schema.

    Raises:
        HTTP 400 if role_name is not one of the four seeded roles.
        HTTP 409 if Supabase rejects the email as already registered.
        HTTP 502 if the Supabase Admin API call fails unexpectedly.
    """
    role = _get_role_by_name(role_name, session)

    # Supabase Admin API call — happens outside the DB transaction.
    try:
        response = supabase.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
    except Exception as exc:
        error_msg = str(exc)
        if "already been registered" in error_msg or "already exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{email}' is already registered in Supabase Auth.",
            ) from exc
        logger.error(
            "Supabase Admin API create_user failed for email=%s: %s",
            email,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Supabase Auth user. Provisioning aborted.",
        ) from exc

    supabase_uuid: str = response.user.id

    # DB write — if this fails, the Supabase user is orphaned. Log the UUID.
    # Only the add+flush pair is caught here; the audit write is outside the
    # handler so a spurious audit failure does not trigger the orphan warning.
    app_user = AppUser(
        supabase_uuid=supabase_uuid,
        role_id=role.role_id,
        email=email,
        is_active=True,
    )
    session.add(app_user)
    try:
        session.flush()  # populate app_user.user_id via RETURNING
    except Exception as exc:
        logger.warning(
            "APP_USER INSERT failed after Supabase user creation. "
            "Orphaned Supabase UUID: %s (email=%s). Manual cleanup required.",
            supabase_uuid,
            email,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Supabase Auth user was created but the APP_USER database record "
                "could not be saved. Contact an administrator."
            ),
        ) from exc

    write_audit_entry(
        session,
        table_name="app_user",
        record_id=str(app_user.user_id),
        action_type="INSERT",
        new_values={"email": email, "role_name": role_name, "supabase_uuid": supabase_uuid},
        changed_by=actor_user_id,
    )

    return app_user, role.role_name


def deactivate_user(
    *,
    user_id: int,
    session: Session,
    supabase: Client,
    actor_user_id: int,
) -> AppUser:
    """Set APP_USER.is_active=False and ban the Supabase Auth user.

    The APP_USER row is never deleted — audit integrity requires it to remain.
    The Supabase ban duration is set to a practical maximum (~100 years).

    Args:
        user_id: APP_USER.user_id of the user to deactivate.
        session: Active SQLAlchemy session; caller owns the commit.
        supabase: Authenticated Supabase client (service-role key).
        actor_user_id: user_id of the Admin performing the action (for audit).

    Returns:
        The updated AppUser instance (not yet committed).

    Raises:
        HTTP 404 if user_id is not found in APP_USER.
        HTTP 409 if the user is already inactive.
        HTTP 502 if the Supabase Admin API ban call fails.
    """
    app_user = session.get(AppUser, user_id)
    if app_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with user_id={user_id} not found.",
        )
    if not app_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with user_id={user_id} is already inactive.",
        )

    old_values = {"is_active": True}

    # Supabase ban — happens before the DB update so that if the ban fails we
    # do not mark the user as inactive in our DB while still active in Supabase.
    try:
        supabase.auth.admin.update_user_by_id(
            app_user.supabase_uuid,
            {"ban_duration": _SUPABASE_BAN_DURATION_PERMANENT},
        )
    except Exception as exc:
        logger.error(
            "Supabase Admin API update_user_by_id failed for supabase_uuid=%s: %s",
            app_user.supabase_uuid,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to ban Supabase Auth user. Deactivation aborted.",
        ) from exc

    app_user.is_active = False

    write_audit_entry(
        session,
        table_name="app_user",
        record_id=str(user_id),
        action_type="UPDATE",
        old_values=old_values,
        new_values={"is_active": False},
        changed_by=actor_user_id,
    )

    return app_user
