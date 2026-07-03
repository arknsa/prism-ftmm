"""Authentication router — /auth/register, /auth/login, /auth/me (P2).

Design (D-031, D-036, D-043):
  - Supabase Auth is the authentication provider (issues JWTs).
  - The app DB is the single source of truth for authorization (APP_USER →
    ROLE → ROLE_PERMISSION). Roles/permissions are NEVER read from JWT claims.
  - The backend is stateless: /auth/login relays Supabase tokens; nothing is
    persisted server-side.

Endpoints:
  POST /auth/register — Admin-only (user:manage). Reuses the provision_user
                        flow: creates a Supabase Auth user + APP_USER with an
                        Admin-assigned role. Self-service signup is intentionally
                        NOT offered — roles are assigned, not self-selected.
  POST /auth/login    — Public. Proxies Supabase's password grant, then confirms
                        the caller is an active APP_USER before returning tokens.
  GET  /auth/me       — Any authenticated user. Returns role + permissions loaded
                        from the app DB (identical contract to GET /me).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from supabase import Client, create_client

from app.config import get_settings
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.dependencies.rbac import require_permission
from app.rate_limiting import login_rate_limit
from app.schemas.auth import AuthenticatedUser, LoginRequest, LoginResponse
from app.schemas.me import MeResponse
from app.schemas.users import UserCreateRequest, UserCreateResponse
from app.services.authentication import authenticate_user
from app.services.user_provisioning import provision_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_supabase_client() -> Client:
    """Build a Supabase client authenticated with the service-role key.

    Raises HTTP 503 if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY are not set.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is not configured.",
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _get_supabase_anon_client() -> Client:
    """Build a Supabase client authenticated with the anon (publishable) key.

    Used for the user-facing login flow so Supabase Auth's own brute-force
    protection stays in effect (the service-role key would bypass it).

    Raises HTTP 503 if SUPABASE_URL or SUPABASE_ANON_KEY are not set.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is not configured.",
        )
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@router.post(
    "/register",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register (provision) a new application user",
)
def register(
    body: UserCreateRequest,
    actor: AuthenticatedUser = Depends(require_permission("user:manage")),
    session: Session = Depends(get_session),
) -> UserCreateResponse:
    """Create a Supabase Auth user and the matching APP_USER row.

    Requires the ``user:manage`` permission (Admin only) — registration is an
    administrative action that assigns a role; it is not public self-service.

    Raises:
        HTTP 400 — unknown role_name.
        HTTP 401 — missing/invalid JWT.
        HTTP 403 — caller lacks user:manage.
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


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain Supabase session tokens",
)
def login(
    body: LoginRequest,
    _rl: None = Depends(login_rate_limit),
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Validate credentials via Supabase and return session tokens.

    Public endpoint (no JWT required — this is where tokens are issued). Rate
    limited per source IP (H1); Supabase Auth adds per-account throttling because
    this flow uses the anon key. The password is validated by Supabase; the app
    DB then decides whether the user may proceed. Role/permissions are obtained
    separately from GET /auth/me.

    Raises:
        HTTP 401 — invalid email/password.
        HTTP 403 — user not provisioned in APP_USER or inactive (D-043).
        HTTP 429 — too many login attempts from this IP.
        HTTP 502 — Supabase Auth call failed.
        HTTP 503 — Supabase not configured.
    """
    supabase = _get_supabase_anon_client()
    app_user, tokens = authenticate_user(
        email=body.email,
        password=body.password,
        session=session,
        supabase=supabase,
    )
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        expires_at=tokens.expires_at,
        user_id=app_user.user_id,
        supabase_uuid=app_user.supabase_uuid,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Authenticated user identity, role, and permissions",
)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    """Return the caller's role and permission list, loaded from the app DB.

    Requires a valid Supabase-issued JWT.

    Raises:
        HTTP 401 — invalid/missing token.
        HTTP 403 — the Supabase UUID is not a registered/active APP_USER.
    """
    return MeResponse(
        user_id=user.user_id,
        supabase_uuid=user.supabase_uuid,
        role=user.role_name,
        permissions=sorted(user.permissions),
    )
