"""Unit tests for app.services.authentication.authenticate_user (P2).

Covers the login proxy in full isolation:
- The Supabase Client is a MagicMock (no real Supabase connection).
- DB access uses create_autospec(Session, instance=True) (Phase 1 pattern).

Design (D-043): Supabase validates the password (authentication); the app DB
decides whether the user may proceed (authorization) — a valid Supabase login
for a user who is absent from or inactive in APP_USER is rejected with 403.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest
from app.models.security import AppUser
from app.services.authentication import authenticate_user
from fastapi import HTTPException
from sqlalchemy.orm import Session

_TEST_EMAIL = "curator@ftmm.ac.id"
_TEST_PASSWORD = "SecurePass123!"
_TEST_SUPABASE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_app_user(is_active: bool = True) -> AppUser:
    user = AppUser()
    user.user_id = 10
    user.supabase_uuid = _TEST_SUPABASE_UUID
    user.role_id = 2
    user.email = _TEST_EMAIL
    user.is_active = is_active
    return user


def _mock_session(app_user: AppUser | None) -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.scalars.return_value.first.return_value = app_user
    return session


def _mock_supabase_ok(uuid: str = _TEST_SUPABASE_UUID) -> MagicMock:
    client = MagicMock()
    supa_session = MagicMock()
    supa_session.access_token = "access-abc"
    supa_session.refresh_token = "refresh-xyz"
    supa_session.token_type = "bearer"
    supa_session.expires_in = 3600
    supa_session.expires_at = 1_900_000_000
    supa_user = MagicMock()
    supa_user.id = uuid
    client.auth.sign_in_with_password.return_value = MagicMock(session=supa_session, user=supa_user)
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_authenticate_returns_app_user_and_tokens() -> None:
    app_user = _make_app_user()
    result_user, tokens = authenticate_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        session=_mock_session(app_user),
        supabase=_mock_supabase_ok(),
    )
    assert result_user is app_user
    assert tokens.access_token == "access-abc"
    assert tokens.refresh_token == "refresh-xyz"
    assert tokens.token_type == "bearer"
    assert tokens.expires_in == 3600
    assert tokens.expires_at == 1_900_000_000


def test_authenticate_looks_up_by_supabase_uuid_from_token() -> None:
    """The DB lookup uses the UUID Supabase returns, never the request email alone."""
    app_user = _make_app_user()
    session = _mock_session(app_user)
    authenticate_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        session=session,
        supabase=_mock_supabase_ok(),
    )
    session.scalars.assert_called_once()


# ---------------------------------------------------------------------------
# Authentication failure (Supabase)
# ---------------------------------------------------------------------------


def test_authenticate_invalid_credentials_raises_401() -> None:
    client = MagicMock()
    client.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            email=_TEST_EMAIL,
            password="wrong",
            session=_mock_session(_make_app_user()),
            supabase=client,
        )
    assert exc.value.status_code == 401


def test_authenticate_missing_session_raises_401() -> None:
    client = MagicMock()
    client.auth.sign_in_with_password.return_value = MagicMock(session=None, user=None)
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            session=_mock_session(_make_app_user()),
            supabase=client,
        )
    assert exc.value.status_code == 401


def test_authenticate_unexpected_supabase_error_raises_502() -> None:
    client = MagicMock()
    client.auth.sign_in_with_password.side_effect = Exception("connection reset by peer")
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            session=_mock_session(_make_app_user()),
            supabase=client,
        )
    assert exc.value.status_code == 502


# ---------------------------------------------------------------------------
# Authorization failure (app DB) — D-043
# ---------------------------------------------------------------------------


def test_authenticate_unprovisioned_user_raises_403() -> None:
    """Valid Supabase login but no APP_USER row → 403."""
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            session=_mock_session(None),
            supabase=_mock_supabase_ok(),
        )
    assert exc.value.status_code == 403


def test_authenticate_inactive_user_raises_403() -> None:
    """Valid Supabase login but APP_USER.is_active is False → 403."""
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            session=_mock_session(_make_app_user(is_active=False)),
            supabase=_mock_supabase_ok(),
        )
    assert exc.value.status_code == 403
