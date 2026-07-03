"""Identity endpoint — GET /me (P2.3).

Returns the authenticated user's role and permission list. This endpoint
requires only a valid JWT (any authenticated user may inspect their own
identity) — no specific permission is gated here.

It is the canonical Phase 2 integration-test target: a working response
confirms that JWT verification, APP_USER resolution, and RBAC loading
all function end-to-end (D-032, D-036, D-043).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthenticatedUser
from app.schemas.me import MeResponse

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=MeResponse, summary="Authenticated user identity")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    """Return the caller's role and permission list.

    Requires a valid Supabase-issued JWT in the Authorization header.
    Raises HTTP 401 for an invalid/missing token; HTTP 403 if the
    Supabase UUID is not registered as an APP_USER.
    """
    return MeResponse(
        user_id=user.user_id,
        supabase_uuid=user.supabase_uuid,
        role=user.role_name,
        permissions=sorted(user.permissions),
    )
