"""Full migration verification against a real PostgreSQL database (H2, Step 2.1).

Decision 2: the migration chain must be fully reversible —
    upgrade -> head, downgrade -> base, upgrade -> head again,
and every individual migration's downgrade() must succeed.

Each test runs against its own throwaway ephemeral database (see conftest).
"""

from __future__ import annotations

import pytest
from app.db import Base

pytestmark = pytest.mark.integration

# The full set of domain tables the models declare (auto-tracks the schema).
_EXPECTED_TABLES: set[str] = set(Base.metadata.tables)
_HEAD_REVISION = "0010"


def test_migration_chain_has_single_head(alembic_heads: list[str]) -> None:
    """The scripts must resolve to exactly one head (no accidental branches)."""
    assert alembic_heads == [_HEAD_REVISION]


def test_upgrade_head_stamps_expected_revision(migration_harness) -> None:
    migration_harness.upgrade("head")
    assert migration_harness.current_revision() == _HEAD_REVISION


def test_upgrade_head_creates_all_domain_tables(migration_harness) -> None:
    migration_harness.upgrade("head")
    live = migration_harness.table_names()
    missing = _EXPECTED_TABLES - live
    assert not missing, f"tables missing after upgrade head: {sorted(missing)}"


def test_full_downgrade_upgrade_round_trip(migration_harness) -> None:
    """upgrade head -> downgrade base -> upgrade head, verifying each stage."""
    # up
    migration_harness.upgrade("head")
    assert migration_harness.current_revision() == _HEAD_REVISION
    assert migration_harness.table_names() >= _EXPECTED_TABLES

    # down to base — all domain tables removed, version cleared
    migration_harness.downgrade("base")
    assert migration_harness.current_revision() is None
    remaining = _EXPECTED_TABLES & migration_harness.table_names()
    assert not remaining, f"tables still present after downgrade base: {sorted(remaining)}"

    # back up — schema fully rebuilt (proves upgrade is repeatable post-downgrade,
    # e.g. the validationstatus enum is dropped and recreated cleanly)
    migration_harness.upgrade("head")
    assert migration_harness.current_revision() == _HEAD_REVISION
    assert migration_harness.table_names() >= _EXPECTED_TABLES


def test_every_migration_downgrades_stepwise(migration_harness, revision_count: int) -> None:
    """Walk the chain down one revision at a time, exercising each downgrade()."""
    migration_harness.upgrade("head")

    for _ in range(revision_count):
        migration_harness.downgrade("-1")

    assert migration_harness.current_revision() is None
    assert _EXPECTED_TABLES.isdisjoint(migration_harness.table_names())

    # And it climbs all the way back.
    migration_harness.upgrade("head")
    assert migration_harness.current_revision() == _HEAD_REVISION
