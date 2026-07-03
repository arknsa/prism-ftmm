"""Auth-related Pydantic schemas (P2.1, P2.2).

TokenClaims: the decoded payload extracted from a Supabase-issued JWT.
AuthenticatedUser: the resolved identity + authorization loaded from the app DB.

Design (D-043): Supabase Auth = authentication (JWT / sub claim).
App DB = authorization (APP_USER → ROLE → ROLE_PERMISSION). Roles are
NEVER read from JWT claims; permissions are loaded exclusively from the DB.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenClaims(BaseModel):
    """Decoded, validated claims from a Supabase-issued JWT.

    Only the fields that the app uses are captured; the full payload may contain
    additional Supabase-specific claims which are intentionally ignored.
    """

    sub: str = Field(..., description="Supabase user UUID — the authentication identity.")
    exp: int = Field(..., description="Token expiry timestamp (Unix epoch seconds).")
    role: str | None = Field(
        default=None,
        description=(
            "JWT role claim issued by Supabase (e.g. 'authenticated'). "
            "Captured for logging only — NEVER used for authorization (D-043)."
        ),
    )


class AuthenticatedUser(BaseModel):
    """Fully resolved authenticated + authorized user (D-043).

    Populated by the get_current_user dependency after DB lookup. This is the
    object that all downstream route handlers receive; it contains everything
    needed to make an authorization decision without hitting the DB again.
    """

    user_id: int = Field(..., description="APP_USER primary key.")
    supabase_uuid: str = Field(..., description="Supabase user UUID (matches JWT sub).")
    role_name: str = Field(..., description="Assigned role name (e.g. 'Admin').")
    permissions: frozenset[str] = Field(
        ...,
        description=(
            "Set of permission names granted to this user's role "
            "(e.g. frozenset({'alumni:read', 'career:read'})). "
            "Loaded from ROLE_PERMISSION — never from JWT claims."
        ),
    )

    model_config = ConfigDict(frozen=True)


class LoginRequest(BaseModel):
    """Body for POST /auth/login. Credentials are forwarded to Supabase Auth."""

    email: EmailStr = Field(..., description="Registered Supabase Auth email address.")
    password: str = Field(
        ...,
        min_length=1,
        description="Account password. Forwarded to Supabase; never stored in the app DB.",
    )


class LoginResponse(BaseModel):
    """Response body for a successful POST /auth/login (HTTP 200).

    Carries the Supabase-issued session tokens plus the caller's app identity.
    Role and permissions are intentionally NOT included here — the client obtains
    them from GET /auth/me, which loads them from the app DB (D-043).
    """

    access_token: str = Field(..., description="Supabase-issued JWT access token.")
    refresh_token: str = Field(..., description="Supabase refresh token for renewing the session.")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer').")
    expires_in: int = Field(..., description="Access-token lifetime in seconds.")
    expires_at: int | None = Field(
        default=None, description="Access-token expiry as a Unix epoch timestamp, if provided."
    )
    user_id: int = Field(..., description="APP_USER primary key of the authenticated user.")
    supabase_uuid: str = Field(..., description="Supabase user UUID (matches the JWT sub claim).")
