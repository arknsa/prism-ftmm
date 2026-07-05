"""Dedup-workflow schema verification against real PostgreSQL (H2, Step 2.5).

Covers dedup_candidate rules via real SQL behavior — only those NOT already
exercised by test_constraints.py (which covers the staging_row -> dedup_candidate
CASCADE, the resolved_by SET NULL, and idx_* existence):

- matched_alumni_id -> alumni ON DELETE CASCADE,
- FK existence (orphan staging_row_id / matched_alumni_id rejected),
- resolution server default ('pending'),
- pending candidates allow NULL resolved_by / resolved_at,
- resolution lifecycle (pending -> merge with resolved_by + resolved_at),
- pending-queue filtering (mirrors get_pending_candidates).

Reuses the shared factories and the shared ``engine`` fixture (conftest); each
test runs on its own migrated ephemeral database. No shared helper is modified.
"""

from __future__ import annotations

import pytest
from factories import (
    _alumni,
    _app_user,
    _count,
    _dedup_candidate,
    _import_batch,
    _role,
    _source,
    _staging_row,
    _study_program,
)
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

_UUID = "33333333-3333-3333-3333-333333333333"


def _parents(conn) -> tuple[int, int]:
    """Insert the minimal parents for a dedup_candidate.

    Returns (staging_row_id, alumni_id). File-private helper (not a shared
    factory) to avoid repeating the parent chain in every test.
    """
    src = _source(conn)
    batch = _import_batch(conn, src)
    staging_row_id = _staging_row(conn, batch)
    study = _study_program(conn)
    alumni_id = _alumni(conn, study, src)
    return staging_row_id, alumni_id


# ---------------------------------------------------------------------------
# Foreign keys — CASCADE from alumni, and existence
# ---------------------------------------------------------------------------


def test_dedup_matched_alumni_delete_cascades(engine: Engine) -> None:
    with engine.begin() as conn:
        srow, alum = _parents(conn)
        _dedup_candidate(conn, srow, alum)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alumni WHERE alumni_id = :a"), {"a": alum})
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate WHERE matched_alumni_id = :a",
            {"a": alum},
        )
        == 0
    )


def test_dedup_rejects_orphan_staging_row(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        src = _source(conn)
        study = _study_program(conn)
        alum = _alumni(conn, study, src)
        conn.execute(
            text(
                "INSERT INTO dedup_candidate (staging_row_id, matched_alumni_id) "
                "VALUES (999999, :a)"
            ),
            {"a": alum},
        )


def test_dedup_rejects_orphan_matched_alumni(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        srow = _staging_row(conn, batch)
        conn.execute(
            text(
                "INSERT INTO dedup_candidate (staging_row_id, matched_alumni_id) "
                "VALUES (:s, 999999)"
            ),
            {"s": srow},
        )


# ---------------------------------------------------------------------------
# Server default & nullability of the pending state
# ---------------------------------------------------------------------------


def test_dedup_resolution_defaults_pending(engine: Engine) -> None:
    with engine.begin() as conn:
        srow, alum = _parents(conn)
        cand = _dedup_candidate(conn, srow, alum)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate "
            "WHERE dedup_candidate_id = :c AND resolution = 'pending'",
            {"c": cand},
        )
        == 1
    )


def test_dedup_pending_fields_are_nullable(engine: Engine) -> None:
    with engine.begin() as conn:
        srow, alum = _parents(conn)
        cand = _dedup_candidate(conn, srow, alum)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate "
            "WHERE dedup_candidate_id = :c AND resolved_by IS NULL AND resolved_at IS NULL",
            {"c": cand},
        )
        == 1
    )


# ---------------------------------------------------------------------------
# Resolution lifecycle & pending-queue filtering
# ---------------------------------------------------------------------------


def test_dedup_resolution_lifecycle(engine: Engine) -> None:
    """A pending candidate is resolved to 'merge' with resolver + timestamp."""
    with engine.begin() as conn:
        srow, alum = _parents(conn)
        role = _role(conn)
        user = _app_user(conn, role, uuid=_UUID)
        cand = _dedup_candidate(conn, srow, alum)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE dedup_candidate SET resolution = 'merge', resolved_by = :u, "
                "resolved_at = now() WHERE dedup_candidate_id = :c"
            ),
            {"u": user, "c": cand},
        )
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate WHERE dedup_candidate_id = :c "
            "AND resolution = 'merge' AND resolved_by = :u AND resolved_at IS NOT NULL",
            {"c": cand, "u": user},
        )
        == 1
    )


def test_dedup_filter_pending_candidates(engine: Engine) -> None:
    """get_pending_candidates shape: only resolution='pending' rows are returned.

    Uses distinct parents per candidate so the result depends on the resolution
    filter, not on whether duplicate (staging_row, alumni) pairs are permitted.
    """
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        study = _study_program(conn)
        s1, a1 = _staging_row(conn, batch, row_number=2), _alumni(conn, study, src, full_name="A")
        s2, a2 = _staging_row(conn, batch, row_number=3), _alumni(conn, study, src, full_name="B")
        s3, a3 = _staging_row(conn, batch, row_number=4), _alumni(conn, study, src, full_name="C")
        _dedup_candidate(conn, s1, a1)  # pending (default)
        _dedup_candidate(conn, s2, a2)  # pending (default)
        conn.execute(
            text(
                "INSERT INTO dedup_candidate (staging_row_id, matched_alumni_id, resolution) "
                "VALUES (:s, :a, 'merge')"
            ),
            {"s": s3, "a": a3},
        )
    assert _count(engine, "SELECT count(*) FROM dedup_candidate", {}) == 3
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate WHERE resolution = 'pending'",
            {},
        )
        == 2
    )
