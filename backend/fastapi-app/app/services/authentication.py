"""Login proxy service (P2).

authenticate_user proxies Supabase's password grant, then enforces the app-DB
authorization gate before returning the session tokens.

Design constraints (D-043, D-031, D-036):
  - Supabase Auth validates the password and issues the JWT (authentication).
  - The app DB is the single source of truth for authorization: a valid Supabase
    login is only honored if the caller exists in APP_USER and is active. The
    role/permissions themselves are never taken from the JWT — they are loaded
    from the DB by get_current_user on each request.
  - The backend stays stateless: no session is persisted here; the Supabase
    tokens are relayed to the caller, who presents them on subsequent requests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from supabase import Client

from app.models.security import AppUser

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SupabaseTokens:
    """The subset of a Supabase session the API relays to the caller."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    expires_at: int | None


def authenticate_user(
    *,
    email: str,
    password: str,
    session: Session,
    supabase: Client,
) -> tuple[AppUser, SupabaseTokens]:
    """Validate credentials via Supabase and confirm the caller is an active APP_USER.

    Args:
        email: Login email, forwarded to Supabase Auth.
        password: Login password, forwarded to Supabase Auth (never stored).
        session: Active SQLAlchemy session (read-only here).
        supabase: Supabase client used for the password grant.

    Returns:
        (app_user, tokens) — the resolved APP_USER and the relayed session tokens.

    Raises:
        HTTP 401 — invalid credentials or Supabase returned no session.
        HTTP 403 — the user is not provisioned in APP_USER or is inactive (D-043).
        HTTP 502 — the Supabase Auth call failed unexpectedly.
    """
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        message = str(exc)
        # gotrue returns "Invalid login credentials" for a bad email/password pair.
        if "invalid" in message.lower() or "credentials" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        logger.error("Supabase sign_in_with_password failed for email=%s: %s", email, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication service failed. Please try again later.",
        ) from exc

    supa_session = response.session
    supa_user = response.user
    if supa_session is None or supa_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Authorization gate: resolve by the UUID Supabase authenticated, not the raw email.
    app_user = session.scalars(select(AppUser).where(AppUser.supabase_uuid == supa_user.id)).first()
    if app_user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not provisioned in the application registry.",
        )
    if not app_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    tokens = SupabaseTokens(
        access_token=supa_session.access_token,
        refresh_token=supa_session.refresh_token,
        token_type=supa_session.token_type,
        expires_in=supa_session.expires_in,
        expires_at=supa_session.expires_at,
    )
    return app_user, tokens
