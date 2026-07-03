"""Tests for GET /me and the require_permission guard (P2.3).

Strategy: use FastAPI's dependency_overrides to inject a synthetic
AuthenticatedUser instead of hitting a real DB or Supabase. This keeps
tests fast, hermetic, and free of external credentials.

The test also covers require_permission() through a dedicated test route
mounted on a fresh app instance — this avoids mutating the application
singleton used by other test modules.

Decisions: D-032, D-036, D-043.
"""

from __future__ import annotations

import pytest
from app.dependencies.auth import get_current_user
from app.dependencies.rbac import require_permission
from app.main import create_app
from app.schemas.auth import AuthenticatedUser
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_ADMIN_USER = AuthenticatedUser(
    user_id=1,
    supabase_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    role_name="Admin",
    permissions=frozenset(
        [
            "alumni:read",
            "alumni:write",
            "alumni:validate",
            "alumni:delete",
            "career:read",
            "career:write",
            "company:read",
            "company:write",
            "import:run",
            "dedup:review",
            "snapshot:manage",
            "audit:read",
            "user:manage",
            "analytics:read",
        ]
    ),
)

_READ_ONLY_USER = AuthenticatedUser(
    user_id=2,
    supabase_uuid="11111111-2222-3333-4444-555555555555",
    role_name="Read Only",
    permissions=frozenset(["alumni:read", "career:read", "company:read", "analytics:read"]),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app_with_user(user: AuthenticatedUser) -> FastAPI:
    """Create a test app instance with get_current_user overridden to return ``user``."""
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _app_with_401() -> FastAPI:
    """Create a test app instance where get_current_user always raises HTTP 401."""

    def _raise_401() -> AuthenticatedUser:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    app = create_app()
    app.dependency_overrides[get_current_user] = _raise_401
    return app


# ---------------------------------------------------------------------------
# GET /me — happy path
# ---------------------------------------------------------------------------


def test_me_returns_200_for_authenticated_user() -> None:
    """Valid authenticated user → 200."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    response = client.get("/me")
    assert response.status_code == 200


def test_me_response_contains_user_id() -> None:
    """Response body includes the correct user_id."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    assert body["user_id"] == _ADMIN_USER.user_id


def test_me_response_contains_supabase_uuid() -> None:
    """Response body includes the correct supabase_uuid."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    assert body["supabase_uuid"] == _ADMIN_USER.supabase_uuid


def test_me_response_role_matches_role_name() -> None:
    """Response 'role' field matches AuthenticatedUser.role_name (D-043)."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    assert body["role"] == "Admin"


def test_me_response_permissions_is_sorted_list() -> None:
    """Permissions are returned as a sorted list for stable serialization."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    permissions = body["permissions"]
    assert isinstance(permissions, list)
    assert permissions == sorted(permissions)


def test_me_response_permissions_match_user_permissions() -> None:
    """Returned permissions match exactly the user's permission set."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    assert set(body["permissions"]) == _ADMIN_USER.permissions


def test_me_admin_has_14_permissions() -> None:
    """Admin user has all 14 permissions per ROLE_PERMISSION_MATRIX.md."""
    client = TestClient(_app_with_user(_ADMIN_USER))
    body = client.get("/me").json()
    assert len(body["permissions"]) == 14


def test_me_read_only_has_4_permissions() -> None:
    """Read Only user has exactly 4 permissions per ROLE_PERMISSION_MATRIX.md."""
    client = TestClient(_app_with_user(_READ_ONLY_USER))
    body = client.get("/me").json()
    assert len(body["permissions"]) == 4


def test_me_read_only_role_is_correct() -> None:
    """Read Only role name is returned correctly."""
    client = TestClient(_app_with_user(_READ_ONLY_USER))
    body = client.get("/me").json()
    assert body["role"] == "Read Only"


# ---------------------------------------------------------------------------
# GET /me — authentication failure
# ---------------------------------------------------------------------------


def test_me_returns_401_when_authentication_fails() -> None:
    """Missing/invalid JWT propagates as HTTP 401."""
    client = TestClient(_app_with_401())
    response = client.get("/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# require_permission — guard behaviour
# Tests use a minimal scratch app with two routes to isolate the guard.
# ---------------------------------------------------------------------------


@pytest.fixture()
def guarded_app() -> FastAPI:
    """Minimal app with two guarded routes and get_current_user overridden."""
    app = FastAPI()

    @app.get("/needs-alumni-read")
    def _needs_alumni_read(
        user: AuthenticatedUser = Depends(require_permission("alumni:read")),
    ) -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/needs-user-manage")
    def _needs_user_manage(
        user: AuthenticatedUser = Depends(require_permission("user:manage")),
    ) -> dict[str, str]:
        return {"ok": "true"}

    return app


def test_require_permission_passes_when_user_holds_permission(
    guarded_app: FastAPI,
) -> None:
    """Authenticated user with the required permission → 200."""
    guarded_app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    client = TestClient(guarded_app)
    response = client.get("/needs-alumni-read")
    assert response.status_code == 200


def test_require_permission_raises_403_when_permission_absent(
    guarded_app: FastAPI,
) -> None:
    """Read Only user lacks user:manage → 403."""
    guarded_app.dependency_overrides[get_current_user] = lambda: _READ_ONLY_USER
    client = TestClient(guarded_app)
    response = client.get("/needs-user-manage")
    assert response.status_code == 403


def test_require_permission_403_detail_is_descriptive(
    guarded_app: FastAPI,
) -> None:
    """403 response includes a non-empty detail message."""
    guarded_app.dependency_overrides[get_current_user] = lambda: _READ_ONLY_USER
    client = TestClient(guarded_app)
    body = client.get("/needs-user-manage").json()
    assert body.get("detail")


def test_require_permission_passes_for_read_only_on_allowed_route(
    guarded_app: FastAPI,
) -> None:
    """Read Only user holds alumni:read → 200 on /needs-alumni-read."""
    guarded_app.dependency_overrides[get_current_user] = lambda: _READ_ONLY_USER
    client = TestClient(guarded_app)
    response = client.get("/needs-alumni-read")
    assert response.status_code == 200


def test_require_permission_propagates_401_from_upstream(
    guarded_app: FastAPI,
) -> None:
    """If get_current_user raises 401 (bad JWT), the guard propagates it."""

    def _raise_401() -> AuthenticatedUser:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    guarded_app.dependency_overrides[get_current_user] = _raise_401
    client = TestClient(guarded_app)
    response = client.get("/needs-alumni-read")
    assert response.status_code == 401


def test_require_permission_returns_authenticated_user_on_success(
    guarded_app: FastAPI,
) -> None:
    """The guard returns the AuthenticatedUser so route handlers receive it."""
    received: list[AuthenticatedUser] = []

    app = FastAPI()

    @app.get("/capture")
    def _capture(
        user: AuthenticatedUser = Depends(require_permission("alumni:read")),
    ) -> dict[str, int]:
        received.append(user)
        return {"user_id": user.user_id}

    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    client = TestClient(app)
    response = client.get("/capture")

    assert response.status_code == 200
    assert response.json()["user_id"] == _ADMIN_USER.user_id
    assert len(received) == 1
    assert received[0] is _ADMIN_USER


def test_different_permission_guards_are_independent(
    guarded_app: FastAPI,
) -> None:
    """Two guards for different permissions operate independently."""
    guarded_app.dependency_overrides[get_current_user] = lambda: _READ_ONLY_USER
    client = TestClient(guarded_app)

    # alumni:read → permitted
    assert client.get("/needs-alumni-read").status_code == 200
    # user:manage → forbidden
    assert client.get("/needs-user-manage").status_code == 403
