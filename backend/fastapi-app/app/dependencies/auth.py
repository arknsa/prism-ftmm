"""Authentication dependencies for FastAPI routes (P2.1, P2.2).

Two injectable dependencies:

1. verify_jwt(authorization)  →  TokenClaims
   Validates the Supabase-issued JWT from the Authorization header and returns
   the decoded claims. Raises HTTP 401 on any JWT failure.

2. get_current_user(claims, session)  →  AuthenticatedUser
   Looks up APP_USER by the Supabase UUID from the claims, loads the role and
   all permissions via ROLE_PERMISSION, and returns a typed AuthenticatedUser.
   Raises HTTP 403 if the user is unknown or inactive.

Design constraints (D-043):
  - Supabase Auth = authentication only (issues JWT; sub = user UUID).
  - App DB = authorization (APP_USER → ROLE → ROLE_PERMISSION).
  - Roles are NEVER read from JWT claims; permissions come exclusively from DB.
  - D-036: least privilege; DB never exposed directly; all rules in backend.
"""

from __future__ import annotations

import logging

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models.security import AppUser, Permission, Role, RolePermission
from app.schemas.auth import AuthenticatedUser, TokenClaims

logger = logging.getLogger(__name__)

# Supabase issues HS256 tokens signed with the project JWT secret.
_ALGORITHM = "HS256"


def verify_jwt(
    authorization: str = Header(..., alias="Authorization"),
) -> TokenClaims:
    """Validate a Supabase-issued JWT and return its decoded claims.

    Expects the standard ``Authorization: Bearer <token>`` header.
    Raises HTTP 401 for any failure: missing header, malformed token,
    invalid signature, or expired token.

    The JWT ``role`` claim (e.g. "authenticated") is captured for logging
    only — it is NEVER used for authorization (D-043).
    """
    settings = get_settings()

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header. Expected: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[_ALGORITHM],
            # Supabase JWTs include aud="authenticated". We do not validate audience
            # because the secret is already project-scoped and FastAPI does not have
            # a fixed audience identifier to assert against.
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    exp = payload.get("exp")
    if not isinstance(sub, str) or sub == "" or not isinstance(exp, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_role = payload.get("role")
    role_str = jwt_role if isinstance(jwt_role, str) else None

    return TokenClaims(sub=sub, exp=exp, role=role_str)


def get_current_user(
    claims: TokenClaims = Depends(verify_jwt),
    session: Session = Depends(get_session),
) -> AuthenticatedUser:
    """Resolve the authenticated user from the app DB using the JWT sub claim.

    Loads APP_USER by Supabase UUID, joins ROLE and ROLE_PERMISSION to build
    the full permission set. Raises HTTP 403 if the UUID is not found in the
    app DB or the user account is inactive (is_active = false).

    Returns AuthenticatedUser with role_name and permissions loaded exclusively
    from the app DB — never from JWT claims (D-043).
    """
    stmt = (
        select(AppUser, Role)
        .join(Role, AppUser.role_id == Role.role_id)
        .where(AppUser.supabase_uuid == claims.sub)
    )
    row = session.execute(stmt).first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found in application registry.",
        )

    app_user, role = row

    if not app_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    perm_stmt = (
        select(Permission.permission_name)
        .join(RolePermission, Permission.permission_id == RolePermission.permission_id)
        .where(RolePermission.role_id == role.role_id)
    )
    permission_names = session.scalars(perm_stmt).all()

    return AuthenticatedUser(
        user_id=app_user.user_id,
        supabase_uuid=app_user.supabase_uuid,
        role_name=role.role_name,
        permissions=frozenset(permission_names),
    )
