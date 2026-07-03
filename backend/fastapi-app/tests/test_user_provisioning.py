"""Unit tests for app.services.user_provisioning (P2.4).

Tests cover provision_user and deactivate_user in full isolation:
- No real Supabase connection: the Supabase Client is replaced with a
  MagicMock in every test.
- No real database: DB interactions use create_autospec(Session, instance=True),
  consistent with the Phase 1 / S1 test pattern.

Decisions: D-031, D-036, D-043.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest
from app.models.security import AppUser, Role
from app.services.user_provisioning import deactivate_user, provision_user
from fastapi import HTTPException
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ADMIN_ACTOR_ID = 1
_TEST_EMAIL = "curator@ftmm.ac.id"
_TEST_PASSWORD = "SecurePass123!"
_TEST_ROLE_NAME = "Data Curator"
_TEST_SUPABASE_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _mock_session() -> MagicMock:
    """Spec-constrained SQLAlchemy Session mock (Phase 1 pattern)."""
    return create_autospec(Session, instance=True)


def _make_role(role_id: int = 2, role_name: str = _TEST_ROLE_NAME) -> Role:
    role = Role()
    role.role_id = role_id
    role.role_name = role_name
    return role


def _make_app_user(
    user_id: int = 10,
    supabase_uuid: str = _TEST_SUPABASE_UUID,
    role_id: int = 2,
    is_active: bool = True,
    email: str = _TEST_EMAIL,
) -> AppUser:
    user = AppUser()
    user.user_id = user_id
    user.supabase_uuid = supabase_uuid
    user.role_id = role_id
    user.is_active = is_active
    user.email = email
    return user


def _mock_supabase_client(supabase_uuid: str = _TEST_SUPABASE_UUID) -> MagicMock:
    """Return a Supabase Client mock with a successful create_user response."""
    client = MagicMock()
    user_obj = MagicMock()
    user_obj.id = supabase_uuid
    client.auth.admin.create_user.return_value = MagicMock(user=user_obj)
    client.auth.admin.update_user_by_id.return_value = MagicMock()
    return client


def _setup_scalars_for_role(session: MagicMock, role: Role | None) -> None:
    """Wire session.scalars().first() to return role (or None)."""
    scalars_result = MagicMock()
    scalars_result.first.return_value = role
    session.scalars.return_value = scalars_result


# ---------------------------------------------------------------------------
# provision_user — happy path
# ---------------------------------------------------------------------------


def test_provision_user_returns_app_user_and_role_name() -> None:
    """Successful provision returns (AppUser, role_name_str)."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)

    # session.flush() populates user_id via side_effect on the added AppUser
    def _flush_side_effect() -> None:
        # Simulate the DB assigning user_id after flush
        added: AppUser = session.add.call_args[0][0]
        added.user_id = 10

    session.flush.side_effect = _flush_side_effect

    app_user, returned_role_name = provision_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        role_name=_TEST_ROLE_NAME,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    assert returned_role_name == _TEST_ROLE_NAME
    assert app_user.supabase_uuid == _TEST_SUPABASE_UUID
    assert app_user.email == _TEST_EMAIL
    assert app_user.role_id == role.role_id
    assert app_user.is_active is True


def test_provision_user_calls_supabase_create_user() -> None:
    """Supabase Admin create_user is called with email, password, email_confirm."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "user_id", 10)

    provision_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        role_name=_TEST_ROLE_NAME,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    supabase.auth.admin.create_user.assert_called_once_with(
        {"email": _TEST_EMAIL, "password": _TEST_PASSWORD, "email_confirm": True}
    )


def test_provision_user_adds_app_user_to_session() -> None:
    """provision_user calls session.add() with an AppUser and an AuditLog."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    session.flush.side_effect = lambda: setattr(session.add.call_args_list[0][0][0], "user_id", 10)

    provision_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        role_name=_TEST_ROLE_NAME,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    # session.add is called twice: once for AppUser, once for AuditLog
    assert session.add.call_count == 2
    first_added = session.add.call_args_list[0][0][0]
    assert isinstance(first_added, AppUser)


def test_provision_user_calls_session_flush() -> None:
    """provision_user flushes the session to obtain the generated user_id."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "user_id", 10)

    provision_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        role_name=_TEST_ROLE_NAME,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    session.flush.assert_called_once()


def test_provision_user_does_not_commit() -> None:
    """provision_user does not commit — the caller owns the transaction."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "user_id", 10)

    provision_user(
        email=_TEST_EMAIL,
        password=_TEST_PASSWORD,
        role_name=_TEST_ROLE_NAME,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# provision_user — failure modes
# ---------------------------------------------------------------------------


def test_provision_user_raises_400_for_unknown_role() -> None:
    """Unknown role_name raises HTTP 400."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    _setup_scalars_for_role(session, None)  # role not found

    with pytest.raises(HTTPException) as exc_info:
        provision_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            role_name="Nonexistent Role",
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 400


def test_provision_user_does_not_call_supabase_when_role_invalid() -> None:
    """Supabase is not called when the role lookup fails (fail fast)."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    _setup_scalars_for_role(session, None)

    with pytest.raises(HTTPException):
        provision_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            role_name="Nonexistent Role",
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    supabase.auth.admin.create_user.assert_not_called()


def test_provision_user_raises_409_when_email_already_registered() -> None:
    """Supabase 'already registered' error maps to HTTP 409."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    supabase.auth.admin.create_user.side_effect = Exception("User already been registered")

    with pytest.raises(HTTPException) as exc_info:
        provision_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            role_name=_TEST_ROLE_NAME,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 409


def test_provision_user_raises_502_when_supabase_fails_unexpectedly() -> None:
    """Unexpected Supabase API error maps to HTTP 502."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    supabase.auth.admin.create_user.side_effect = Exception("Network error")

    with pytest.raises(HTTPException) as exc_info:
        provision_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            role_name=_TEST_ROLE_NAME,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 502


def test_provision_user_raises_500_when_db_write_fails() -> None:
    """DB INSERT failure after Supabase creation maps to HTTP 500."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    role = _make_role()
    _setup_scalars_for_role(session, role)
    session.flush.side_effect = Exception("DB constraint violation")

    with pytest.raises(HTTPException) as exc_info:
        provision_user(
            email=_TEST_EMAIL,
            password=_TEST_PASSWORD,
            role_name=_TEST_ROLE_NAME,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# deactivate_user — happy path
# ---------------------------------------------------------------------------


def test_deactivate_user_sets_is_active_false() -> None:
    """Successful deactivation sets app_user.is_active to False."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user

    result = deactivate_user(
        user_id=app_user.user_id,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    assert result.is_active is False


def test_deactivate_user_calls_supabase_ban() -> None:
    """deactivate_user calls update_user_by_id with ban_duration."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user

    deactivate_user(
        user_id=app_user.user_id,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    supabase.auth.admin.update_user_by_id.assert_called_once_with(
        app_user.supabase_uuid, {"ban_duration": "876600h"}
    )


def test_deactivate_user_does_not_commit() -> None:
    """deactivate_user does not commit — the caller owns the transaction."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user

    deactivate_user(
        user_id=app_user.user_id,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    session.commit.assert_not_called()


def test_deactivate_user_does_not_delete_app_user_row() -> None:
    """APP_USER row is never deleted — audit integrity."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user

    deactivate_user(
        user_id=app_user.user_id,
        session=session,
        supabase=supabase,
        actor_user_id=_ADMIN_ACTOR_ID,
    )

    session.delete.assert_not_called()


# ---------------------------------------------------------------------------
# deactivate_user — failure modes
# ---------------------------------------------------------------------------


def test_deactivate_user_raises_404_when_user_not_found() -> None:
    """Non-existent user_id raises HTTP 404."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        deactivate_user(
            user_id=999,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 404


def test_deactivate_user_raises_409_when_already_inactive() -> None:
    """Deactivating an already-inactive user raises HTTP 409."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=False)
    session.get.return_value = app_user

    with pytest.raises(HTTPException) as exc_info:
        deactivate_user(
            user_id=app_user.user_id,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 409


def test_deactivate_user_raises_502_when_supabase_ban_fails() -> None:
    """Supabase ban API failure raises HTTP 502."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user
    supabase.auth.admin.update_user_by_id.side_effect = Exception("Network error")

    with pytest.raises(HTTPException) as exc_info:
        deactivate_user(
            user_id=app_user.user_id,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    assert exc_info.value.status_code == 502


def test_deactivate_user_does_not_mutate_db_when_supabase_fails() -> None:
    """If the Supabase ban fails, is_active is not changed in the session."""
    session = _mock_session()
    supabase = _mock_supabase_client()
    app_user = _make_app_user(is_active=True)
    session.get.return_value = app_user
    supabase.auth.admin.update_user_by_id.side_effect = Exception("Network error")

    with pytest.raises(HTTPException):
        deactivate_user(
            user_id=app_user.user_id,
            session=session,
            supabase=supabase,
            actor_user_id=_ADMIN_ACTOR_ID,
        )

    # is_active must remain True because the ban call failed before mutation
    assert app_user.is_active is True
