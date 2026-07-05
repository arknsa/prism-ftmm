"""Unit tests for app.dependencies.auth (P2.1, P2.2).

Both verify_jwt and get_current_user are tested in pure isolation:
- No real Supabase connection.
- No real database: DB interactions use create_autospec(Session, instance=True),
  consistent with the Phase 1 test pattern established in test_audit_service.py.
- JWTs are generated with jwt.encode() using the same secret that verify_jwt
  will decode them with, injected via monkeypatching Settings.

Decisions: D-032, D-036, D-043.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import jwt
import pytest
from app.dependencies.auth import get_current_user, verify_jwt
from app.models.security import AppUser, Role
from app.schemas.auth import AuthenticatedUser, TokenClaims
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_TEST_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TEST_SUPABASE_URL = "https://testproject.supabase.co"
_TEST_ISSUER = f"{_TEST_SUPABASE_URL}/auth/v1"

# ES256 keypair used to sign test tokens; verify_jwt receives the public key via a
# patched JWKS client (no network). A second key models a wrong/foreign signer.
_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def _make_token(
    sub: str | None = _TEST_UUID,
    exp_offset: int = 3600,
    private_key: ec.EllipticCurvePrivateKey = _PRIVATE_KEY,
    issuer: str = _TEST_ISSUER,
    include_role: bool = True,
) -> str:
    """Build an ES256-signed JWT for testing."""
    payload: dict[str, Any] = {"exp": int(time.time()) + exp_offset, "iss": issuer}
    if sub is not None:
        payload["sub"] = sub
    if include_role:
        payload["role"] = "authenticated"
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": "test-kid"})


def _bearer(token: str) -> str:
    return f"Bearer {token}"


@contextmanager
def _patched_verify(
    supabase_url: str | None = _TEST_SUPABASE_URL,
    signing_key: object = _PUBLIC_KEY,
) -> Iterator[None]:
    """Patch settings.supabase_url and the JWKS client used by verify_jwt.

    The JWKS client is mocked to return ``signing_key`` for any token, so no
    network access occurs; the real ES256 signature check still runs in jwt.decode.
    """
    with (
        patch("app.dependencies.auth.get_settings") as mock_settings,
        patch("app.dependencies.auth._get_jwk_client") as mock_client,
    ):
        mock_settings.return_value.supabase_url = supabase_url
        mock_client.return_value.get_signing_key_from_jwt.return_value.key = signing_key
        yield


def _mock_session() -> MagicMock:
    """Spec-constrained SQLAlchemy Session mock (Phase 1 pattern)."""
    return create_autospec(Session, instance=True)


# ---------------------------------------------------------------------------
# Helpers: build ORM-like objects for DB query mocking
# ---------------------------------------------------------------------------


def _make_role(role_id: int = 1, role_name: str = "Admin") -> Role:
    role = Role()
    role.role_id = role_id
    role.role_name = role_name
    return role


def _make_app_user(
    user_id: int = 10,
    supabase_uuid: str = _TEST_UUID,
    role_id: int = 1,
    is_active: bool = True,
) -> AppUser:
    user = AppUser()
    user.user_id = user_id
    user.supabase_uuid = supabase_uuid
    user.role_id = role_id
    user.is_active = is_active
    return user


# ---------------------------------------------------------------------------
# verify_jwt — happy path
# ---------------------------------------------------------------------------


def test_verify_jwt_returns_token_claims() -> None:
    """Valid ES256 token → TokenClaims with correct sub and exp."""
    token = _make_token()
    with _patched_verify():
        claims = verify_jwt(_bearer(token))

    assert isinstance(claims, TokenClaims)
    assert claims.sub == _TEST_UUID


def test_verify_jwt_captures_role_claim_for_logging() -> None:
    """JWT role claim is captured into TokenClaims.role (for logging only)."""
    token = _make_token()
    with _patched_verify():
        claims = verify_jwt(_bearer(token))

    assert claims.role == "authenticated"


def test_verify_jwt_role_claim_is_none_when_absent() -> None:
    """JWT without a role claim produces TokenClaims.role = None."""
    token = _make_token(include_role=False)
    with _patched_verify():
        claims = verify_jwt(_bearer(token))

    assert claims.role is None


# ---------------------------------------------------------------------------
# verify_jwt — failure modes
# ---------------------------------------------------------------------------


def test_verify_jwt_raises_503_when_service_unconfigured() -> None:
    """Missing SUPABASE_URL → HTTP 503 (service misconfigured)."""
    token = _make_token()
    with _patched_verify(supabase_url=None), pytest.raises(HTTPException) as exc_info:
        verify_jwt(_bearer(token))

    assert exc_info.value.status_code == 503


def test_verify_jwt_raises_401_for_missing_bearer_scheme() -> None:
    """Authorization header without 'Bearer' scheme → HTTP 401."""
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt("Token sometoken")

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_empty_token() -> None:
    """'Bearer ' with no token → HTTP 401."""
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt("Bearer ")

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_wrong_signing_key() -> None:
    """Token signed by a key other than the JWKS public key → HTTP 401."""
    token = _make_token(private_key=_OTHER_PRIVATE_KEY)
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_expired_token() -> None:
    """Expired token (exp in the past) → HTTP 401."""
    token = _make_token(exp_offset=-10)
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_wrong_issuer() -> None:
    """Token whose 'iss' does not match the project issuer → HTTP 401."""
    token = _make_token(issuer="https://evil.supabase.co/auth/v1")
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_malformed_token() -> None:
    """Gibberish string → HTTP 401."""
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt("Bearer not.a.jwt")

    assert exc_info.value.status_code == 401


def test_verify_jwt_raises_401_for_missing_sub_claim() -> None:
    """Token without 'sub' claim → HTTP 401 (missing required claim)."""
    token = _make_token(sub=None)
    with _patched_verify(), pytest.raises(HTTPException) as exc_info:
        verify_jwt(_bearer(token))

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user — happy path
# ---------------------------------------------------------------------------


def _setup_session_for_user(
    session: MagicMock,
    app_user: AppUser,
    role: Role,
    permission_names: list[str],
) -> None:
    """Wire session.execute() and session.scalars() to return test data."""
    execute_result = MagicMock()
    execute_result.first.return_value = (app_user, role)
    session.execute.return_value = execute_result

    scalars_result = MagicMock()
    scalars_result.all.return_value = permission_names
    session.scalars.return_value = scalars_result


def test_get_current_user_returns_authenticated_user() -> None:
    """Valid claims + known active user → AuthenticatedUser."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600, role="authenticated")
    session = _mock_session()
    role = _make_role(role_id=1, role_name="Admin")
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read", "alumni:write"])

    result = get_current_user(claims, session)

    assert isinstance(result, AuthenticatedUser)


def test_get_current_user_user_id_matches_app_user() -> None:
    """AuthenticatedUser.user_id matches the APP_USER primary key."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user(user_id=42)
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    result = get_current_user(claims, session)

    assert result.user_id == 42


def test_get_current_user_supabase_uuid_matches_claims_sub() -> None:
    """AuthenticatedUser.supabase_uuid matches the JWT sub claim (D-043)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, [])

    result = get_current_user(claims, session)

    assert result.supabase_uuid == _TEST_UUID


def test_get_current_user_role_name_loaded_from_db_not_jwt() -> None:
    """role_name comes from the app DB Role row, NOT from the JWT claims (D-043)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600, role="authenticated")
    session = _mock_session()
    role = _make_role(role_name="Data Curator")
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    result = get_current_user(claims, session)

    assert result.role_name == "Data Curator"
    assert result.role_name != claims.role  # JWT claim is irrelevant to authorization


def test_get_current_user_permissions_loaded_from_db() -> None:
    """permissions is a frozenset of names loaded from ROLE_PERMISSION (D-043)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role(role_name="Admin")
    app_user = _make_app_user()
    expected = {"alumni:read", "alumni:write", "alumni:delete", "user:manage"}
    _setup_session_for_user(session, app_user, role, list(expected))

    result = get_current_user(claims, session)

    assert result.permissions == frozenset(expected)


def test_get_current_user_permissions_is_frozenset() -> None:
    """permissions is exactly a frozenset (not a list or set)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    result = get_current_user(claims, session)

    assert isinstance(result.permissions, frozenset)


def test_get_current_user_empty_permissions_for_no_mappings() -> None:
    """A role with zero ROLE_PERMISSION rows yields an empty permissions set."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role(role_name="Read Only")
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, [])

    result = get_current_user(claims, session)

    assert result.permissions == frozenset()


# ---------------------------------------------------------------------------
# get_current_user — failure modes
# ---------------------------------------------------------------------------


def test_get_current_user_raises_403_when_uuid_not_in_app_db() -> None:
    """UUID from JWT sub not found in APP_USER → HTTP 403."""
    claims = TokenClaims(sub="unknown-uuid", exp=int(time.time()) + 3600)
    session = _mock_session()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    session.execute.return_value = execute_result

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(claims, session)

    assert exc_info.value.status_code == 403


def test_get_current_user_raises_403_when_user_is_inactive() -> None:
    """APP_USER with is_active=False → HTTP 403."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user(is_active=False)
    execute_result = MagicMock()
    execute_result.first.return_value = (app_user, role)
    session.execute.return_value = execute_result

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(claims, session)

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# get_current_user — DB query behavior
# ---------------------------------------------------------------------------


def test_get_current_user_calls_execute_once_for_user_lookup() -> None:
    """session.execute() is called exactly once (user+role join)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    get_current_user(claims, session)

    assert session.execute.call_count == 1


def test_get_current_user_calls_scalars_once_for_permissions() -> None:
    """session.scalars() is called exactly once (permission lookup)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    get_current_user(claims, session)

    assert session.scalars.call_count == 1


def test_get_current_user_does_not_commit_or_flush() -> None:
    """User resolution must not commit or flush (read-only DB interaction)."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user()
    _setup_session_for_user(session, app_user, role, ["alumni:read"])

    get_current_user(claims, session)

    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_get_current_user_skips_permission_query_when_user_not_found() -> None:
    """When APP_USER lookup fails, no permission query is made."""
    claims = TokenClaims(sub="unknown-uuid", exp=int(time.time()) + 3600)
    session = _mock_session()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    session.execute.return_value = execute_result

    with pytest.raises(HTTPException):
        get_current_user(claims, session)

    session.scalars.assert_not_called()


def test_get_current_user_skips_permission_query_when_user_is_inactive() -> None:
    """When APP_USER is inactive, no permission query is made."""
    claims = TokenClaims(sub=_TEST_UUID, exp=int(time.time()) + 3600)
    session = _mock_session()
    role = _make_role()
    app_user = _make_app_user(is_active=False)
    execute_result = MagicMock()
    execute_result.first.return_value = (app_user, role)
    session.execute.return_value = execute_result

    with pytest.raises(HTTPException):
        get_current_user(claims, session)

    session.scalars.assert_not_called()
