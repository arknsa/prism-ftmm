"""Shared insert factories for PostgreSQL integration tests.

Each helper inserts a single row and returns its primary key, running inside the
caller's transaction (the caller owns commit/rollback). Extracted verbatim from
test_constraints.py so future integration test files (RBAC, import, dedup) reuse
them instead of duplicating. Behavior is identical to the originals — this module
introduces no new logic.
"""

from __future__ import annotations

from sqlalchemy import Engine, text


def _role(conn, name: str = "Admin") -> int:
    return conn.execute(
        text("INSERT INTO role (role_name) VALUES (:n) RETURNING role_id"), {"n": name}
    ).scalar_one()


def _permission(conn, name: str = "alumni:read") -> int:
    return conn.execute(
        text("INSERT INTO permission (permission_name) VALUES (:n) RETURNING permission_id"),
        {"n": name},
    ).scalar_one()


def _role_permission(conn, role_id: int, permission_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO role_permission (role_id, permission_id) " "VALUES (:r, :p) RETURNING id"
        ),
        {"r": role_id, "p": permission_id},
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
