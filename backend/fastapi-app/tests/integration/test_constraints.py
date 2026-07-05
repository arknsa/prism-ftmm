"""Constraint verification against a real PostgreSQL database (H2, Step 2.2).

Every rule is validated by **real SQL behavior** — actual INSERT/UPDATE/DELETE
against a freshly-migrated ephemeral database — not by inspecting metadata. The
only catalog query is the index-existence check (an index's presence cannot be
meaningfully behavior-tested).

Each test reuses the ``migration_harness`` fixture (own throwaway DB, migrated to
head) via the local ``engine`` fixture, so tests are fully isolated.
"""

from __future__ import annotations

import pytest
from factories import (
    _alumni,
    _app_user,
    _audit_log,
    _career,
    _company,
    _company_alias,
    _count,
    _dedup_candidate,
    _import_batch,
    _industry,
    _permission,
    _role,
    _source,
    _staging_row,
    _study_program,
)
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Foreign keys — existence (child with non-existent parent is rejected)
# ---------------------------------------------------------------------------


def test_fk_rejects_orphan_company_alias(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _company_alias(conn, company_id=999999)


def test_fk_rejects_orphan_career_record(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        src = _source(conn)
        _company(conn)
        # alumni_id 999999 does not exist
        conn.execute(
            text(
                "INSERT INTO career_record (alumni_id, company_id, role_title, source_id) "
                "VALUES (999999, 1, 'X', :s)"
            ),
            {"s": src},
        )


# ---------------------------------------------------------------------------
# Foreign keys — ON DELETE CASCADE
# ---------------------------------------------------------------------------


def test_cascade_company_to_alias(engine: Engine) -> None:
    with engine.begin() as conn:
        comp = _company(conn)
        _company_alias(conn, comp)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM company WHERE company_id = :c"), {"c": comp})
    assert (
        _count(engine, "SELECT count(*) FROM company_alias WHERE company_id = :c", {"c": comp}) == 0
    )


def test_cascade_import_batch_to_staging_rows(engine: Engine) -> None:
    with engine.begin() as conn:
        src = _source(conn)
        batch = _import_batch(conn, src)
        _staging_row(conn, batch)
        _staging_row(conn, batch, row_number=3)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM import_batch WHERE batch_id = :b"), {"b": batch})
    assert _count(engine, "SELECT count(*) FROM staging_row WHERE batch_id = :b", {"b": batch}) == 0


def test_cascade_alumni_to_career_records(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src, comp = _study_program(conn), _source(conn), _company(conn)
        alum = _alumni(conn, sp, src)
        _career(conn, alum, comp, src)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alumni WHERE alumni_id = :a"), {"a": alum})
    assert (
        _count(engine, "SELECT count(*) FROM career_record WHERE alumni_id = :a", {"a": alum}) == 0
    )


def test_cascade_staging_row_to_dedup_candidate(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        alum = _alumni(conn, sp, src)
        batch = _import_batch(conn, src)
        srow = _staging_row(conn, batch)
        _dedup_candidate(conn, srow, alum)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM staging_row WHERE staging_row_id = :s"), {"s": srow})
    assert (
        _count(
            engine, "SELECT count(*) FROM dedup_candidate WHERE staging_row_id = :s", {"s": srow}
        )
        == 0
    )


# ---------------------------------------------------------------------------
# Foreign keys — ON DELETE RESTRICT (parent delete blocked while referenced)
# ---------------------------------------------------------------------------


def test_restrict_study_program_referenced_by_alumni(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        _alumni(conn, sp, src)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM study_program WHERE program_id = :p"), {"p": sp})


def test_restrict_capture_source_referenced_by_alumni(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        _alumni(conn, sp, src)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM capture_source WHERE source_id = :s"), {"s": src})


def test_restrict_company_referenced_by_career(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src, comp = _study_program(conn), _source(conn), _company(conn)
        alum = _alumni(conn, sp, src)
        _career(conn, alum, comp, src)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM company WHERE company_id = :c"), {"c": comp})


# ---------------------------------------------------------------------------
# Foreign keys — ON DELETE SET NULL
# ---------------------------------------------------------------------------


def test_set_null_company_industry(engine: Engine) -> None:
    with engine.begin() as conn:
        ind = _industry(conn)
        comp = _company(conn, industry_id=ind)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM industry WHERE industry_id = :i"), {"i": ind})
    assert (
        _count(
            engine,
            "SELECT count(*) FROM company WHERE company_id = :c AND industry_id IS NULL",
            {"c": comp},
        )
        == 1
    )


def test_set_null_audit_log_changed_by(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        user = _app_user(conn, role, uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        audit = _audit_log(conn, changed_by=user)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app_user WHERE user_id = :u"), {"u": user})
    assert (
        _count(
            engine,
            "SELECT count(*) FROM audit_log WHERE audit_id = :a AND changed_by IS NULL",
            {"a": audit},
        )
        == 1
    )


def test_set_null_dedup_candidate_resolved_by(engine: Engine) -> None:
    with engine.begin() as conn:
        role = _role(conn)
        user = _app_user(conn, role, uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        sp, src = _study_program(conn), _source(conn)
        alum = _alumni(conn, sp, src)
        batch = _import_batch(conn, src)
        srow = _staging_row(conn, batch)
        cand = _dedup_candidate(conn, srow, alum, resolved_by=user)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM app_user WHERE user_id = :u"), {"u": user})
    assert (
        _count(
            engine,
            "SELECT count(*) FROM dedup_candidate "
            "WHERE dedup_candidate_id = :d AND resolved_by IS NULL",
            {"d": cand},
        )
        == 1
    )


# ---------------------------------------------------------------------------
# Unique constraints
# ---------------------------------------------------------------------------


def test_unique_company_canonical_name(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _company(conn, name="DupCo")
        _company(conn, name="DupCo")


def test_unique_company_alias_name(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        c1 = _company(conn, name="C1")
        c2 = _company(conn, name="C2")
        _company_alias(conn, c1, name="same-alias")
        _company_alias(conn, c2, name="same-alias")


def test_unique_role_name(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _role(conn, name="Curator")
        _role(conn, name="Curator")


def test_unique_permission_name(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _permission(conn, name="alumni:write")
        _permission(conn, name="alumni:write")


def test_unique_app_user_supabase_uuid(engine: Engine) -> None:
    dup = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    with pytest.raises(IntegrityError), engine.begin() as conn:
        r1 = _role(conn, name="R1")
        r2 = _role(conn, name="R2")
        _app_user(conn, r1, uuid=dup)
        _app_user(conn, r2, uuid=dup)


# ---------------------------------------------------------------------------
# Partial unique index — alumni.linkedin_url (unique when NOT NULL)
# ---------------------------------------------------------------------------


def test_partial_unique_linkedin_rejects_duplicate_non_null(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        _alumni(conn, sp, src, full_name="A", linkedin_url="https://linkedin.com/in/x")
        _alumni(conn, sp, src, full_name="B", linkedin_url="https://linkedin.com/in/x")


def test_partial_unique_linkedin_allows_multiple_nulls(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        _alumni(conn, sp, src, full_name="A", linkedin_url=None)
        _alumni(conn, sp, src, full_name="B", linkedin_url=None)
    assert _count(engine, "SELECT count(*) FROM alumni WHERE linkedin_url IS NULL", {}) == 2


# ---------------------------------------------------------------------------
# Partial unique index — one is_current=true career record per alumnus
# ---------------------------------------------------------------------------


def test_partial_unique_one_current_job_rejected(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as conn:
        sp, src, comp = _study_program(conn), _source(conn), _company(conn)
        alum = _alumni(conn, sp, src)
        _career(conn, alum, comp, src, is_current=True)
        _career(conn, alum, comp, src, is_current=True)


def test_partial_unique_allows_many_non_current(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src, comp = _study_program(conn), _source(conn), _company(conn)
        alum = _alumni(conn, sp, src)
        _career(conn, alum, comp, src, is_current=False)
        _career(conn, alum, comp, src, is_current=False)
    assert (
        _count(engine, "SELECT count(*) FROM career_record WHERE alumni_id = :a", {"a": alum}) == 2
    )


def test_partial_unique_allows_current_for_different_alumni(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src, comp = _study_program(conn), _source(conn), _company(conn)
        a1 = _alumni(conn, sp, src, full_name="A")
        a2 = _alumni(conn, sp, src, full_name="B")
        _career(conn, a1, comp, src, is_current=True)
        _career(conn, a2, comp, src, is_current=True)
    assert _count(engine, "SELECT count(*) FROM career_record WHERE is_current = true", {}) == 2


# ---------------------------------------------------------------------------
# Enum — validationstatus rejects out-of-domain values
# ---------------------------------------------------------------------------


def test_enum_rejects_invalid_validation_status(engine: Engine) -> None:
    with pytest.raises(DBAPIError), engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        conn.execute(
            text(
                "INSERT INTO alumni (full_name, study_program_id, graduation_year, source_id, "
                "validation_status) VALUES ('X', :sp, 2020, :s, 'bogus')"
            ),
            {"sp": sp, "s": src},
        )


def test_enum_accepts_valid_validation_status(engine: Engine) -> None:
    with engine.begin() as conn:
        sp, src = _study_program(conn), _source(conn)
        for status_val in ("pending", "validated", "rejected"):
            conn.execute(
                text(
                    "INSERT INTO alumni (full_name, study_program_id, graduation_year, source_id, "
                    "validation_status) VALUES ('X', :sp, 2020, :s, :st)"
                ),
                {"sp": sp, "s": src, "st": status_val},
            )
    assert _count(engine, "SELECT count(*) FROM alumni", {}) == 3


# ---------------------------------------------------------------------------
# Indexes — every idx_* declared by the migrations must exist
# ---------------------------------------------------------------------------

_EXPECTED_INDEXES = {
    # 0008 — alumni / career / company filter indexes
    "idx_alumni_graduation_year",
    "idx_alumni_study_program",
    "idx_alumni_validation_status",
    "idx_career_company",
    "idx_career_snapshot",
    "idx_career_is_current",
    "idx_career_alumni",
    "idx_company_industry",
    "idx_company_location",
    # 0009 — staging
    "idx_import_batch_source",
    "idx_import_batch_created_by",
    "idx_import_batch_status",
    "idx_staging_row_batch",
    "idx_staging_row_status",
    # 0010 — dedup
    "idx_dedup_candidate_staging_row",
    "idx_dedup_candidate_matched_alumni",
    "idx_dedup_candidate_resolved_by",
    "idx_dedup_candidate_resolution",
}


def test_all_declared_indexes_exist(engine: Engine) -> None:
    with engine.connect() as conn:
        live = set(
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            ).scalars()
        )
    missing = _EXPECTED_INDEXES - live
    assert not missing, f"missing indexes: {sorted(missing)}"
