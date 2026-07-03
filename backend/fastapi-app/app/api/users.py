"""Admin user-provisioning endpoints (P2.4).

POST /users   — provision a new application user (requires user:manage)
DELETE /users/{user_id} — deactivate an application user (requires user:manage)

Both endpoints are Admin-only per ROLE_PERMISSION_MATRIX.md (D-036).
The Supabase Admin SDK client is constructed from settings on each request;
no singleton is cached because the service-role key is secret and must not
leak across request contexts.

Design (D-031, D-036, D-043).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from supabase import Client, create_client

from app.config import get_settings
from app.db import get_session
from app.dependencies.rbac import require_permission
from app.schemas.auth import AuthenticatedUser
from app.schemas.users import UserCreateRequest, UserCreateResponse, UserDeactivateResponse
from app.services.user_provisioning import deactivate_user, provision_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _get_supabase_client() -> Client:
    """Build and return a Supabase client authenticated with the service-role key.

    Raises HTTP 503 if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are not set.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase provisioning service is not configured.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new application user",
)
def create_user(
    body: UserCreateRequest,
    actor: AuthenticatedUser = Depends(require_permission("user:manage")),
    session: Session = Depends(get_session),
) -> UserCreateResponse:
    """Create a Supabase Auth user and the matching APP_USER row.

    Requires the ``user:manage`` permission (Admin role only).

    Raises:
        HTTP 400 — unknown role_name.
        HTTP 403 — caller lacks user:manage permission.
        HTTP 409 — email already registered in Supabase Auth.
        HTTP 502 — Supabase Admin API call failed.
        HTTP 503 — Supabase not configured.
    """
    supabase = _get_supabase_client()
    app_user, role_name = provision_user(
        email=body.email,
        password=body.password,
        role_name=body.role_name,
        session=session,
        supabase=supabase,
        actor_user_id=actor.user_id,
    )
    session.commit()
    session.refresh(app_user)
    return UserCreateResponse(
        user_id=app_user.user_id,
        supabase_uuid=app_user.supabase_uuid,
        email=app_user.email,
        role=role_name,
    )


@router.delete(
    "/{user_id}",
    response_model=UserDeactivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate an application user",
)
def delete_user(
    user_id: int,
    actor: AuthenticatedUser = Depends(require_permission("user:manage")),
    session: Session = Depends(get_session),
) -> UserDeactivateResponse:
    """Deactivate an APP_USER and ban the corresponding Supabase Auth user.

    The APP_USER row is never deleted — audit integrity requires it.
    The Supabase Auth user is banned for ~100 years (effectively permanent).

    Requires the ``user:manage`` permission (Admin role only).

    Raises:
        HTTP 403 — caller lacks user:manage permission.
        HTTP 404 — user_id not found.
        HTTP 409 — user already inactive.
        HTTP 502 — Supabase Admin API call failed.
        HTTP 503 — Supabase not configured.
    """
    supabase = _get_supabase_client()
    app_user = deactivate_user(
        user_id=user_id,
        session=session,
        supabase=supabase,
        actor_user_id=actor.user_id,
    )
    session.commit()
    return UserDeactivateResponse(
        user_id=app_user.user_id,
        supabase_uuid=app_user.supabase_uuid,
        is_active=app_user.is_active,
        detail=f"User {user_id} has been deactivated.",
    )
