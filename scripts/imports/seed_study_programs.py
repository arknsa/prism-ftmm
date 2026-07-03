"""Seed STUDY_PROGRAM with the five approved FTMM programs (D-003, D-004).

Usage:
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/imports/seed_study_programs.py

Idempotent: uses INSERT ... ON CONFLICT (program_name) DO NOTHING.
"""

from __future__ import annotations

import os
import sys

from _utils import normalize_db_url
from sqlalchemy import create_engine, text

# Exact canonical names per D-004; is_ftmm_valid=true for all five programs.
# The sentinel row (Other / Unknown) exists to test rejection logic.
# degree_level is "N/A" for the sentinel: it represents any non-FTMM program
# of unknown or inapplicable degree type (the column is NOT NULL, so a value is required).
STUDY_PROGRAMS: list[dict[str, object]] = [
    {
        "program_name": "Technology of Data Science",
        "degree_level": "S1",
        "is_ftmm_valid": True,
    },
    {
        "program_name": "Industrial Engineering",
        "degree_level": "S1",
        "is_ftmm_valid": True,
    },
    {
        "program_name": "Electrical Engineering",
        "degree_level": "S1",
        "is_ftmm_valid": True,
    },
    {
        "program_name": "Nanotechnology Engineering",
        "degree_level": "S1",
        "is_ftmm_valid": True,
    },
    {
        "program_name": "Robotics and Artificial Intelligence Engineering",
        "degree_level": "S1",
        "is_ftmm_valid": True,
    },
    # Sentinel: catches alumni whose program is outside FTMM scope.
    {"program_name": "Other / Unknown", "degree_level": "N/A", "is_ftmm_valid": False},
]

# RETURNING 1 lets us count actual inserts; rows skipped by ON CONFLICT return nothing.
# conn.execute(text, list) routes to executemany whose rowcount is undefined in psycopg v3.
_INSERT_SQL = text("""
    INSERT INTO study_program (program_name, degree_level, is_ftmm_valid)
    VALUES (:program_name, :degree_level, :is_ftmm_valid)
    ON CONFLICT (program_name) DO NOTHING
    RETURNING 1
    """)


def seed(database_url: str) -> None:
    engine = create_engine(normalize_db_url(database_url), future=True)
    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, STUDY_PROGRAMS)
        inserted = len(result.fetchall())
    print(f"seed_study_programs: {inserted} row(s) inserted (0 = already seeded).")


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    seed(url)


if __name__ == "__main__":
    main()
