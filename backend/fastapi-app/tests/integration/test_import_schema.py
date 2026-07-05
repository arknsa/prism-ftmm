"""Import-pipeline schema verification against real PostgreSQL (H2, Step 2.4).

Covers import_batch / staging_row rules via real SQL behavior — only those NOT
already exercised by test_constraints.py (which covers the import_batch ->
staging_row CASCADE and idx_* existence):

- import_batch.source_id  ON DELETE RESTRICT,
- import_batch.created_by ON DELETE SET NULL, and nullability (CLI/system imports),
- import_batch.status / staging_row.row_status server defaults ('pending'),
- staging_row.batch_id FK existence (orphan rejected),
- staging_row.raw_extra JSONB round-trip,
- batch -> rows status filtering (mirrors GET /imports/{id}/rows?status=).

Reuses the shared factories and the shared ``engine`` fixture (conftest); each
test runs on its own migrated ephemeral database. No shared helper is modified.
"""

from __future__ import annotations

import json

import pytest
from factories import _app_user, _count, _import_batch, _role, _source, _staging_row
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

_UUID = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# import_batch — foreign-key delete behavior
# ---------------------------------------------------------------------------


def test_import_batch_source_delete_is_restricted(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        _import_batch(conn, src)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM capture_source WHERE source_id = :s"), {"s": src})


def test_import_batch_created_by_set_null_on_user_delete(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        role = _role(conn)
        user = _app_user(conn, role, uuid=_UUID)
        batch = _import_batch(conn, src, created_by=user)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app_user WHERE user_id = :u"), {"u": user})
    assert (
        _count(
            engine,
            "SELECT count(*) FROM import_batch WHERE batch_id = :b AND created_by IS NULL",
            {"b": batch},
        )
        == 1
    )


# ---------------------------------------------------------------------------
# import_batch — nullability & server defaults
# ---------------------------------------------------------------------------


def test_import_batch_allows_null_created_by(engine: Engine) -> None:
    """CLI / system imports have no request actor (D-046)."""
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src, created_by=None)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM import_batch WHERE batch_id = :b AND created_by IS NULL",
            {"b": batch},
        )
        == 1
    )


def test_import_batch_status_defaults_pending(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM import_batch WHERE batch_id = :b AND status = 'pending'",
            {"b": batch},
        )
        == 1
    )


# ---------------------------------------------------------------------------
# staging_row — server default, FK existence, JSONB
# ---------------------------------------------------------------------------


def test_staging_row_status_defaults_pending(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        row = _staging_row(conn, batch)
    assert (
        _count(
            engine,
            "SELECT count(*) FROM staging_row WHERE staging_row_id = :r AND row_status = 'pending'",
            {"r": row},
        )
        == 1
    )


def test_staging_row_rejects_orphan_batch(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO staging_row (batch_id, row_number) VALUES (999999, 2)"))


def test_staging_row_raw_extra_jsonb_round_trip(engine: Engine) -> None:
    payload = {"employed_status": "employed", "notes": "n/a", "nested": {"a": 1}}
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        row = conn.execute(
            text(
                "INSERT INTO staging_row (batch_id, row_number, raw_extra) "
                "VALUES (:b, 2, CAST(:x AS JSONB)) RETURNING staging_row_id"
            ),
            {"b": batch, "x": json.dumps(payload)},
        ).scalar_one()
    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT raw_extra FROM staging_row WHERE staging_row_id = :r"),
            {"r": row},
        ).scalar_one()
    assert stored == payload


# ---------------------------------------------------------------------------
# batch -> rows status filtering (EP-3 shape)
# ---------------------------------------------------------------------------


def test_staging_rows_filter_by_status(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        _staging_row(conn, batch, row_number=2)  # pending (default)
        _staging_row(conn, batch, row_number=3)  # pending (default)
        conn.execute(
            text(
                "INSERT INTO staging_row (batch_id, row_number, row_status, row_error) "
                "VALUES (:b, 4, 'error', 'missing field')"
            ),
            {"b": batch},
        )
    assert _count(engine, "SELECT count(*) FROM staging_row WHERE batch_id = :b", {"b": batch}) == 3
    assert (
        _count(
            engine,
            "SELECT count(*) FROM staging_row WHERE batch_id = :b AND row_status = 'pending'",
            {"b": batch},
        )
        == 2
    )
    assert (
        _count(
            engine,
            "SELECT count(*) FROM staging_row WHERE batch_id = :b AND row_status = 'error'",
            {"b": batch},
        )
        == 1
    )
