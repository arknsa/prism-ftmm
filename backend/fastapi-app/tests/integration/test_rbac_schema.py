"""RBAC schema/workflow verification against real PostgreSQL (H2, Step 2.3).

Covers the authorization tables (role, permission, role_permission, app_user) via
real SQL behavior — rules that are specific to RBAC and not already exercised by
test_constraints.py:

- role_permission composite uniqueness and its CASCADE foreign keys,
- app_user.role_id ON DELETE RESTRICT,
- app_user.is_active / timestamp server defaults,
- the role -> role_permission -> permission authorization resolution (D-043).

Reuses the shared factories and the shared ``engine`` fixture (conftest); each
test runs on its own migrated ephemeral database.
"""

from __future__ import annotations

import pytest
from factories import _app_user, _count, _permission, _role, _role_permission
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

_UUID = "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# role_permission — composite uniqueness
# ---------------------------------------------------------------------------


def test_role_permission_rejects_duplicate_pair(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        role = _role(conn)
        perm = _permission(conn)
        _role_permission(conn, role, perm)
        _role_permission(conn, role, perm)


def test_role_permission_allows_distinct_pairs(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        p1 = _permission(conn, name="alumni:read")
        p2 = _permission(conn, name="alumni:write")
        _role_permission(conn, role, p1)
        _role_permission(conn, role, p2)
    assert (
        _count(engine, "SELECT count(*) FROM role_permission WHERE role_id = :r", {"r": role}) == 2
    )


# ---------------------------------------------------------------------------
# role_permission — ON DELETE CASCADE from both parents
# ---------------------------------------------------------------------------


def test_role_permission_cascades_on_role_delete(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        perm = _permission(conn)
        _role_permission(conn, role, perm)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM role WHERE role_id = :r"), {"r": role})
    assert (
        _count(engine, "SELECT count(*) FROM role_permission WHERE role_id = :r", {"r": role}) == 0
    )


def test_role_permission_cascades_on_permission_delete(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        perm = _permission(conn)
        _role_permission(conn, role, perm)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM permission WHERE permission_id = :p"), {"p": perm})
    assert (
        _count(engine, "SELECT count(*) FROM role_permission WHERE permission_id = :p", {"p": perm})
        == 0
    )


# ---------------------------------------------------------------------------
# app_user — role_id is ON DELETE RESTRICT
# ---------------------------------------------------------------------------


def test_app_user_role_delete_is_restricted(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        _app_user(conn, role, uuid=_UUID)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM role WHERE role_id = :r"), {"r": role})


# ---------------------------------------------------------------------------
# app_user — server defaults
# ---------------------------------------------------------------------------


def test_app_user_is_active_defaults_true(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        user = _app_user(conn, role, uuid=_UUID)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM app_user WHERE user_id = :u AND is_active = true",
            {"u": user},
        )
        == 1
    )


def test_app_user_timestamps_are_populated(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        user = _app_user(conn, role, uuid=_UUID)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM app_user "
            "WHERE user_id = :u AND created_at IS NOT NULL AND updated_at IS NOT NULL",
            {"u": user},
        )
        == 1
    )


# ---------------------------------------------------------------------------
# Authorization resolution — role -> role_permission -> permission (D-043)
# ---------------------------------------------------------------------------


def test_role_resolves_to_its_permission_set(engine: Engine) -> None:
    """Mirror the get_current_user permission query; assert the resolved set."""
    with engine.begin() as conn:
        role = _role(conn, name="Data Curator")
        p1 = _permission(conn, name="alumni:read")
        p2 = _permission(conn, name="import:run")
        _permission(conn, name="user:manage")  # exists but NOT granted to this role
        _role_permission(conn, role, p1)
        _role_permission(conn, role, p2)
    with engine.connect() as conn:
        granted = set(
            conn.execute(
                text(
                    "SELECT p.permission_name FROM permission p "
                    "JOIN role_permission rp ON p.permission_id = rp.permission_id "
                    "WHERE rp.role_id = :r"
                ),
                {"r": role},
            ).scalars()
        )
    assert granted == {"alumni:read", "import:run"}


def test_role_without_grants_resolves_to_empty_set(engine: Engine) -> None:
    """A role with no grants resolves to no permissions, even when other
    permissions exist — exercises the same resolution JOIN as the positive case."""
    with engine.begin() as conn:
        role = _role(conn, name="Read Only")
        # Permissions exist in the system but none are granted to this role.
        _permission(conn, name="alumni:read")
        _permission(conn, name="import:run")
    with engine.connect() as conn:
        granted = set(
            conn.execute(
                text(
                    "SELECT p.permission_name FROM permission p "
                    "JOIN role_permission rp ON p.permission_id = rp.permission_id "
                    "WHERE rp.role_id = :r"
                ),
                {"r": role},
            ).scalars()
        )
    assert granted == set()
