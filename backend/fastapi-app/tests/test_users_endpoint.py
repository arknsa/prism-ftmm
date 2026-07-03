"""Integration-style tests for POST /users and DELETE /users/{user_id} (P2.4).

Strategy: FastAPI dependency_overrides to inject synthetic AuthenticatedUser
objects and a no-op Session, plus patch the service-layer functions and
Supabase client, so no real DB or Supabase connection is needed.

Decisions: D-031, D-036, D-043.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, create_autospec, patch

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.security import AppUser
from app.schemas.auth import AuthenticatedUser
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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

_VALID_CREATE_BODY = {
    "email": "curator@ftmm.ac.id",
    "password": "SecurePass123!",
    "role_name": "Data Curator",
}

_TEST_SUPABASE_UUID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _make_provisioned_app_user() -> AppUser:
    user = AppUser()
    user.user_id = 99
    user.supabase_uuid = _TEST_SUPABASE_UUID
    user.role_id = 2
    user.email = "curator@ftmm.ac.id"
    user.is_active = True
    return user


def _make_deactivated_app_user() -> AppUser:
    user = AppUser()
    user.user_id = 5
    user.supabase_uuid = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
    user.role_id = 3
    user.email = "viewer@ftmm.ac.id"
    user.is_active = False
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_override() -> Iterator[MagicMock]:
    """FastAPI override for get_session — yields a spec-constrained mock Session."""
    session = create_autospec(Session, instance=True)
    yield session


def _app_with_admin() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER
    app.dependency_overrides[get_session] = _mock_session_override
    return TestClient(app)


def _app_with_read_only() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _READ_ONLY_USER
    app.dependency_overrides[get_session] = _mock_session_override
    return TestClient(app)


def _app_with_401() -> TestClient:
    def _raise_401() -> AuthenticatedUser:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    app = create_app()
    app.dependency_overrides[get_current_user] = _raise_401
    app.dependency_overrides[get_session] = _mock_session_override
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /users — authorization
# ---------------------------------------------------------------------------


def test_create_user_returns_403_for_non_admin() -> None:
    """Read Only user lacks user:manage → 403."""
    client = _app_with_read_only()
    response = client.post("/users", json=_VALID_CREATE_BODY)
    assert response.status_code == 403


def test_create_user_returns_401_for_unauthenticated() -> None:
    """Missing/invalid JWT → 401."""
    client = _app_with_401()
    response = client.post("/users", json=_VALID_CREATE_BODY)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /users — happy path
# ---------------------------------------------------------------------------


def test_create_user_returns_201_on_success() -> None:
    """Admin + valid body + successful provision → 201."""
    client = _app_with_admin()
    app_user = _make_provisioned_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
        patch("app.api.users.Session"),
    ):
        mock_provision.return_value = (app_user, "Data Curator")
        # session.commit and session.refresh are no-ops in the mock
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.status_code == 201


def test_create_user_response_contains_user_id() -> None:
    """201 response body contains user_id."""
    client = _app_with_admin()
    app_user = _make_provisioned_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (app_user, "Data Curator")
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.json()["user_id"] == app_user.user_id


def test_create_user_response_contains_email() -> None:
    """201 response body contains the provisioned email."""
    client = _app_with_admin()
    app_user = _make_provisioned_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (app_user, "Data Curator")
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.json()["email"] == "curator@ftmm.ac.id"


def test_create_user_response_contains_role() -> None:
    """201 response body contains the assigned role name."""
    client = _app_with_admin()
    app_user = _make_provisioned_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (app_user, "Data Curator")
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.json()["role"] == "Data Curator"


def test_create_user_response_contains_supabase_uuid() -> None:
    """201 response body contains the Supabase Auth user UUID."""
    client = _app_with_admin()
    app_user = _make_provisioned_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (app_user, "Data Curator")
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.json()["supabase_uuid"] == _TEST_SUPABASE_UUID


# ---------------------------------------------------------------------------
# POST /users — service error propagation
# ---------------------------------------------------------------------------


def test_create_user_returns_400_for_unknown_role() -> None:
    """Unknown role_name → 400 (propagated from provision_user)."""
    client = _app_with_admin()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown role 'Ghost'.",
        )
        response = client.post(
            "/users",
            json={"email": "x@ftmm.ac.id", "password": "Pass1234!", "role_name": "Ghost"},
        )

    assert response.status_code == 400


def test_create_user_returns_409_for_duplicate_email() -> None:
    """Duplicate email in Supabase → 409 (propagated from provision_user)."""
    client = _app_with_admin()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.provision_user") as mock_provision,
    ):
        mock_provision.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )
        response = client.post("/users", json=_VALID_CREATE_BODY)

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /users/{user_id} — authorization
# ---------------------------------------------------------------------------


def test_delete_user_returns_403_for_non_admin() -> None:
    """Read Only user lacks user:manage → 403."""
    client = _app_with_read_only()
    response = client.delete("/users/5")
    assert response.status_code == 403


def test_delete_user_returns_401_for_unauthenticated() -> None:
    """Missing/invalid JWT → 401."""
    client = _app_with_401()
    response = client.delete("/users/5")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /users/{user_id} — happy path
# ---------------------------------------------------------------------------


def test_delete_user_returns_200_on_success() -> None:
    """Admin + valid user_id + successful deactivation → 200."""
    client = _app_with_admin()
    app_user = _make_deactivated_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.return_value = app_user
        response = client.delete("/users/5")

    assert response.status_code == 200


def test_delete_user_response_is_active_false() -> None:
    """200 response body has is_active=False."""
    client = _app_with_admin()
    app_user = _make_deactivated_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.return_value = app_user
        response = client.delete("/users/5")

    assert response.json()["is_active"] is False


def test_delete_user_response_contains_user_id() -> None:
    """200 response body contains the user_id."""
    client = _app_with_admin()
    app_user = _make_deactivated_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.return_value = app_user
        response = client.delete("/users/5")

    assert response.json()["user_id"] == 5


def test_delete_user_response_contains_detail_message() -> None:
    """200 response body contains a non-empty detail message."""
    client = _app_with_admin()
    app_user = _make_deactivated_app_user()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.return_value = app_user
        response = client.delete("/users/5")

    assert response.json().get("detail")


# ---------------------------------------------------------------------------
# DELETE /users/{user_id} — service error propagation
# ---------------------------------------------------------------------------


def test_delete_user_returns_404_when_not_found() -> None:
    """Non-existent user_id → 404 (propagated from deactivate_user)."""
    client = _app_with_admin()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
        response = client.delete("/users/999")

    assert response.status_code == 404


def test_delete_user_returns_409_when_already_inactive() -> None:
    """Already-inactive user → 409 (propagated from deactivate_user)."""
    client = _app_with_admin()

    with (
        patch("app.api.users._get_supabase_client"),
        patch("app.api.users.deactivate_user") as mock_deactivate,
    ):
        mock_deactivate.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already inactive.",
        )
        response = client.delete("/users/5")

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /users — input validation
# ---------------------------------------------------------------------------


def test_create_user_returns_422_for_missing_email() -> None:
    """Request body missing email → 422 (Pydantic validation)."""
    client = _app_with_admin()
    response = client.post("/users", json={"password": "Pass1234!", "role_name": "Data Curator"})
    assert response.status_code == 422


def test_create_user_returns_422_for_short_password() -> None:
    """Password shorter than 8 chars → 422 (Pydantic validation)."""
    client = _app_with_admin()
    response = client.post(
        "/users",
        json={"email": "x@ftmm.ac.id", "password": "short", "role_name": "Data Curator"},
    )
    assert response.status_code == 422
