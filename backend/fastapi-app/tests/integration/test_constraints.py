"""Constraint verification against a real PostgreSQL database (H2, Step 2.2).

Every rule is validated by **real SQL behavior** — actual INSERT/UPDATE/DELETE
against a freshly-migrated ephemeral database — not by inspecting metadata. The
only catalog query is the index-existence check (an index's presence cannot be
meaningfully behavior-tested).

Each test reuses the ``migration_harness`` fixture (own throwaway DB, migrated to
head) via the local ``engine`` fixture, so tests are fully isolated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration


@pytest.fixture()
def engine(migration_harness) -> Iterator[Engine]:
    """A fresh ephemeral database migrated to head, exposed as an Engine."""
    migration_harness.upgrade("head")
    eng = create_engine(migration_harness.url)
    try:
        yield eng
    finally:
        eng.dispose()


# ---------------------------------------------------------------------------
# Insert helpers — return the new PK; run inside the caller's transaction.
# ---------------------------------------------------------------------------


def _role(conn, name: str = "Admin") -> int:
    return conn.execute(
        text("INSERT INTO role (role_name) VALUES (:n) RETURNING role_id"), {"n": name}
    ).scalar_one()


def _permission(conn, name: str = "alumni:read") -> int:
    return conn.execute(
        text("INSERT INTO permission (permission_name) VALUES (:n) RETURNING permission_id"),
        {"n": name},
    ).scalar_one()


def _app_user(conn, role_id: int, uuid: str, email: str | None = None) -> int:
    return conn.execute(
        text(
            "INSERT INTO app_user (supabase_uuid, role_id, email) "
            "VALUES (:u, :r, :e) RETURNING user_id"
        ),
        {"u": uuid, "r": role_id, "e": email},
    ).scalar_one()


def _source(conn, source_type: str = "LinkedIn", trust_tier: int = 3) -> int:
    return conn.execute(
        text(
            "INSERT INTO capture_source (source_type, trust_tier) "
            "VALUES (:t, :tt) RETURNING source_id"
        ),
        {"t": source_type, "tt": trust_tier},
    ).scalar_one()


def _study_program(conn, name: str = "Data Science", degree: str = "S1") -> int:
    return conn.execute(
        text(
            "INSERT INTO study_program (program_name, degree_level) "
            "VALUES (:n, :d) RETURNING program_id"
        ),
        {"n": name, "d": degree},
    ).scalar_one()


def _industry(conn, name: str = "Software", sector: str = "Technology") -> int:
    return conn.execute(
        text(
            "INSERT INTO industry (industry_name, sector_name) "
            "VALUES (:n, :s) RETURNING industry_id"
        ),
        {"n": name, "s": sector},
    ).scalar_one()


def _location(conn, country: str = "Indonesia") -> int:
    return conn.execute(
        text("INSERT INTO location (country) VALUES (:c) RETURNING location_id"),
        {"c": country},
    ).scalar_one()


def _company(
    conn, name: str = "Gojek", industry_id: int | None = None, location_id: int | None = None
) -> int:
    return conn.execute(
        text(
            "INSERT INTO company (canonical_name, industry_id, location_id) "
            "VALUES (:n, :i, :l) RETURNING company_id"
        ),
        {"n": name, "i": industry_id, "l": location_id},
    ).scalar_one()


def _company_alias(conn, company_id: int, name: str = "gojek", source_id: int | None = None) -> int:
    return conn.execute(
        text(
            "INSERT INTO company_alias (company_id, alias_name, source_id) "
            "VALUES (:c, :n, :s) RETURNING alias_id"
        ),
        {"c": company_id, "n": name, "s": source_id},
    ).scalar_one()


def _alumni(
    conn,
    study_program_id: int,
    source_id: int,
    full_name: str = "Alum",
    grad_year: int = 2020,
    linkedin_url: str | None = None,
) -> int:
    return conn.execute(
        text(
            "INSERT INTO alumni (full_name, study_program_id, graduation_year, source_id, "
            "linkedin_url) VALUES (:n, :sp, :y, :s, :li) RETURNING alumni_id"
        ),
        {
            "n": full_name,
            "sp": study_program_id,
            "y": grad_year,
            "s": source_id,
            "li": linkedin_url,
        },
    ).scalar_one()


def _snapshot(conn, quarter: str = "2025-Q1") -> int:
    return conn.execute(
        text(
            "INSERT INTO refresh_snapshot (quarter_label, refresh_date) "
            "VALUES (:q, CURRENT_DATE) RETURNING snapshot_id"
        ),
        {"q": quarter},
    ).scalar_one()


def _career(
    conn,
    alumni_id: int,
    company_id: int,
    source_id: int,
    is_current: bool = False,
    snapshot_id: int | None = None,
    role_title: str = "Engineer",
) -> int:
    return conn.execute(
        text(
            "INSERT INTO career_record (alumni_id, company_id, role_title, is_current, "
            "snapshot_id, source_id) VALUES (:a, :c, :r, :cur, :sn, :s) RETURNING career_record_id"
        ),
        {
            "a": alumni_id,
            "c": company_id,
            "r": role_title,
            "cur": is_current,
            "sn": snapshot_id,
            "s": source_id,
        },
    ).scalar_one()


def _import_batch(conn, source_id: int, created_by: int | None = None) -> int:
    return conn.execute(
        text(
            "INSERT INTO import_batch (source_id, filename, total_rows, parsed_rows, error_rows, "
            "created_by) VALUES (:s, 'f.csv', 1, 1, 0, :cb) RETURNING batch_id"
        ),
        {"s": source_id, "cb": created_by},
    ).scalar_one()


def _staging_row(conn, batch_id: int, row_number: int = 2) -> int:
    return conn.execute(
        text(
            "INSERT INTO staging_row (batch_id, row_number) VALUES (:b, :r) "
            "RETURNING staging_row_id"
        ),
        {"b": batch_id, "r": row_number},
    ).scalar_one()


def _dedup_candidate(
    conn, staging_row_id: int, matched_alumni_id: int, resolved_by: int | None = None
) -> int:
    return conn.execute(
        text(
            "INSERT INTO dedup_candidate (staging_row_id, matched_alumni_id, resolved_by) "
            "VALUES (:sr, :a, :rb) RETURNING dedup_candidate_id"
        ),
        {"sr": staging_row_id, "a": matched_alumni_id, "rb": resolved_by},
    ).scalar_one()


def _audit_log(conn, changed_by: int | None = None) -> int:
    return conn.execute(
        text(
            "INSERT INTO audit_log (table_name, record_id, action_type, changed_by) "
            "VALUES ('alumni', '1', 'INSERT', :cb) RETURNING audit_id"
        ),
        {"cb": changed_by},
    ).scalar_one()


def _count(engine: Engine, sql: str, params: dict) -> int:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


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
