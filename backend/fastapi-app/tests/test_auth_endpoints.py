"""Integration-style tests for the /auth router (P2): register, login, me.

Strategy mirrors test_users_endpoint.py / test_me_endpoint.py:
- FastAPI dependency_overrides inject a synthetic AuthenticatedUser and a
  no-op Session so no real DB is touched.
- The Supabase client factory and the service-layer functions are patched, so
  no real Supabase connection is needed.

Design (D-031, D-036, D-043):
- POST /auth/register reuses the Admin-gated provision_user flow (user:manage).
- POST /auth/login proxies Supabase's password grant, then verifies the caller
  is a provisioned, active APP_USER before returning tokens.
- GET  /auth/me returns role + permissions loaded from the app DB.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec, patch

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.security import AppUser
from app.rate_limiting import login_rate_limit
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

_VALID_REGISTER_BODY = {
    "email": "curator@ftmm.ac.id",
    "password": "SecurePass123!",
    "role_name": "Data Curator",
}

_VALID_LOGIN_BODY = {"email": "curator@ftmm.ac.id", "password": "SecurePass123!"}

_TEST_SUPABASE_UUID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _make_app_user() -> AppUser:
    user = AppUser()
    user.user_id = 99
    user.supabase_uuid = _TEST_SUPABASE_UUID
    user.role_id = 2
    user.email = "curator@ftmm.ac.id"
    user.is_active = True
    return user


def _make_tokens() -> SimpleNamespace:
    """Duck-typed stand-in for the login service's SupabaseTokens result."""
    return SimpleNamespace(
        access_token="access-abc",
        refresh_token="refresh-xyz",
        token_type="bearer",
        expires_in=3600,
        expires_at=1_900_000_000,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session_override() -> Iterator[MagicMock]:
    session = create_autospec(Session, instance=True)
    yield session


def _app(user: AuthenticatedUser | None = None) -> TestClient:
    app = create_app()
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = _mock_session_override
    # Disable the per-IP login limiter so shared window state can't bleed between
    # tests; the limiter itself is exercised in test_login_is_rate_limited_returns_429.
    app.dependency_overrides[login_rate_limit] = lambda: None
    return TestClient(app)


def _app_with_401() -> TestClient:
    def _raise_401() -> AuthenticatedUser:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    app = create_app()
    app.dependency_overrides[get_current_user] = _raise_401
    app.dependency_overrides[get_session] = _mock_session_override
    app.dependency_overrides[login_rate_limit] = lambda: None
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


def test_auth_me_returns_200_for_authenticated_user() -> None:
    response = _app(_ADMIN_USER).get("/auth/me")
    assert response.status_code == 200


def test_auth_me_returns_role_and_permissions_from_db() -> None:
    body = _app(_READ_ONLY_USER).get("/auth/me").json()
    assert body["role"] == "Read Only"
    assert set(body["permissions"]) == _READ_ONLY_USER.permissions


def test_auth_me_permissions_sorted() -> None:
    body = _app(_ADMIN_USER).get("/auth/me").json()
    assert body["permissions"] == sorted(body["permissions"])


def test_auth_me_returns_401_when_unauthenticated() -> None:
    response = _app_with_401().get("/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register — authorization (Admin-only, reuses provision_user)
# ---------------------------------------------------------------------------


def test_auth_register_returns_403_for_non_admin() -> None:
    response = _app(_READ_ONLY_USER).post("/auth/register", json=_VALID_REGISTER_BODY)
    assert response.status_code == 403


def test_auth_register_returns_401_for_unauthenticated() -> None:
    response = _app_with_401().post("/auth/register", json=_VALID_REGISTER_BODY)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/register — happy path + error propagation
# ---------------------------------------------------------------------------


def test_auth_register_returns_201_on_success() -> None:
    client = _app(_ADMIN_USER)
    with (
        patch("app.api.auth._get_supabase_client"),
        patch("app.api.auth.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (_make_app_user(), "Data Curator")
        response = client.post("/auth/register", json=_VALID_REGISTER_BODY)
    assert response.status_code == 201


def test_auth_register_response_contains_identity_and_role() -> None:
    client = _app(_ADMIN_USER)
    with (
        patch("app.api.auth._get_supabase_client"),
        patch("app.api.auth.provision_user") as mock_provision,
    ):
        mock_provision.return_value = (_make_app_user(), "Data Curator")
        body = client.post("/auth/register", json=_VALID_REGISTER_BODY).json()
    assert body["user_id"] == 99
    assert body["supabase_uuid"] == _TEST_SUPABASE_UUID
    assert body["email"] == "curator@ftmm.ac.id"
    assert body["role"] == "Data Curator"


def test_auth_register_returns_409_for_duplicate_email() -> None:
    client = _app(_ADMIN_USER)
    with (
        patch("app.api.auth._get_supabase_client"),
        patch("app.api.auth.provision_user") as mock_provision,
    ):
        mock_provision.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered."
        )
        response = client.post("/auth/register", json=_VALID_REGISTER_BODY)
    assert response.status_code == 409


def test_auth_register_returns_400_for_unknown_role() -> None:
    client = _app(_ADMIN_USER)
    with (
        patch("app.api.auth._get_supabase_client"),
        patch("app.api.auth.provision_user") as mock_provision,
    ):
        mock_provision.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role 'Ghost'."
        )
        response = client.post(
            "/auth/register",
            json={"email": "x@ftmm.ac.id", "password": "Pass1234!", "role_name": "Ghost"},
        )
    assert response.status_code == 400


def test_auth_register_returns_422_for_short_password() -> None:
    response = _app(_ADMIN_USER).post(
        "/auth/register",
        json={"email": "x@ftmm.ac.id", "password": "short", "role_name": "Data Curator"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login — public; proxies Supabase then verifies APP_USER
# ---------------------------------------------------------------------------


def test_auth_login_returns_200_and_tokens_on_success() -> None:
    client = _app()  # login is public — no get_current_user override
    with (
        patch("app.api.auth._get_supabase_anon_client"),
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.return_value = (_make_app_user(), _make_tokens())
        response = client.post("/auth/login", json=_VALID_LOGIN_BODY)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == "access-abc"
    assert body["refresh_token"] == "refresh-xyz"
    assert body["token_type"] == "bearer"
    assert body["user_id"] == 99
    assert body["supabase_uuid"] == _TEST_SUPABASE_UUID


def test_auth_login_returns_401_for_invalid_credentials() -> None:
    client = _app()
    with (
        patch("app.api.auth._get_supabase_anon_client"),
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password."
        )
        response = client.post("/auth/login", json=_VALID_LOGIN_BODY)
    assert response.status_code == 401


def test_auth_login_returns_403_for_inactive_or_unprovisioned_user() -> None:
    client = _app()
    with (
        patch("app.api.auth._get_supabase_anon_client"),
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not provisioned in the application registry.",
        )
        response = client.post("/auth/login", json=_VALID_LOGIN_BODY)
    assert response.status_code == 403


def test_auth_login_returns_422_for_missing_password() -> None:
    response = _app().post("/auth/login", json={"email": "x@ftmm.ac.id"})
    assert response.status_code == 422


def test_auth_login_does_not_require_authentication() -> None:
    """Login must be reachable without a JWT (it is the token-issuing endpoint)."""
    client = _app()  # no get_current_user override
    with (
        patch("app.api.auth._get_supabase_anon_client"),
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.return_value = (_make_app_user(), _make_tokens())
        response = client.post("/auth/login", json=_VALID_LOGIN_BODY)
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# H1 — login uses the anon key (not service-role) and is rate limited
# ---------------------------------------------------------------------------


def test_login_uses_anon_key_not_service_role() -> None:
    """Login must build the Supabase client from the ANON key, never service-role."""
    client = _app()
    sentinel = object()
    with (
        patch("app.api.auth._get_supabase_anon_client", return_value=sentinel) as mock_anon,
        patch("app.api.auth._get_supabase_client") as mock_service_role,
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.return_value = (_make_app_user(), _make_tokens())
        resp = client.post("/auth/login", json=_VALID_LOGIN_BODY)

    assert resp.status_code == 200
    mock_anon.assert_called_once()
    mock_service_role.assert_not_called()
    # the anon client is the one handed to the auth service
    assert mock_auth.call_args.kwargs["supabase"] is sentinel


def test_login_is_rate_limited_returns_429() -> None:
    """After the per-IP window is exhausted, further login attempts return 429."""
    from app.rate_limiting import _LOGIN_IP_MAX_CALLS, _login_ip_window

    _login_ip_window.clear()  # deterministic start for the shared limiter

    app = create_app()
    app.dependency_overrides[get_session] = _mock_session_override
    # NOTE: login_rate_limit intentionally NOT overridden here — exercising it.
    c = TestClient(app)

    with (
        patch("app.api.auth._get_supabase_anon_client"),
        patch("app.api.auth.authenticate_user") as mock_auth,
    ):
        mock_auth.return_value = (_make_app_user(), _make_tokens())
        statuses = [
            c.post("/auth/login", json=_VALID_LOGIN_BODY).status_code
            for _ in range(_LOGIN_IP_MAX_CALLS + 1)
        ]

    assert statuses[:_LOGIN_IP_MAX_CALLS] == [200] * _LOGIN_IP_MAX_CALLS
    assert statuses[-1] == 429
    _login_ip_window.clear()  # leave global state clean for other tests


def test_settings_binds_supabase_anon_key(monkeypatch: object) -> None:
    """SUPABASE_ANON_KEY must be bound in Settings (H1/M2)."""
    from app.config import Settings

    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")  # type: ignore[attr-defined]
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.supabase_anon_key == "anon-test-key"
