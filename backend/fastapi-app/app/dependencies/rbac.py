"""RBAC permission-guard dependency factory (P2.3).

Provides require_permission(), a factory that produces a FastAPI dependency
asserting the authenticated user holds a specific permission. Any route that
needs authorization uses this:

    @router.get("/alumni", dependencies=[Depends(require_permission("alumni:read"))])
    # or, when the user object is also needed in the handler:
    def list_alumni(user: AuthenticatedUser = Depends(require_permission("alumni:read"))):
        ...

Design (D-036, D-043):
  - Permission names come exclusively from the app DB via get_current_user.
  - The guard never reads JWT claims; it inspects AuthenticatedUser.permissions.
  - HTTP 403 is returned when the permission is absent; HTTP 401 propagates
    naturally from the upstream get_current_user / verify_jwt dependencies.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.auth import AuthenticatedUser


def require_permission(permission: str) -> Callable[..., AuthenticatedUser]:
    """Return a FastAPI dependency that enforces a single named permission.

    The returned callable resolves the current user (via get_current_user)
    and raises HTTP 403 if the user's permission set does not include
    ``permission``. On success it passes the AuthenticatedUser through,
    so route handlers can receive it directly when needed.

    Args:
        permission: A permission name string (e.g. ``"alumni:read"``).

    Returns:
        A FastAPI-injectable dependency function.
    """

    def _guard(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return user

    # Give the inner function a stable, unique name so FastAPI's dependency
    # cache distinguishes guards for different permissions correctly.
    _guard.__name__ = f"require_permission_{permission.replace(':', '_')}"

    return _guard
