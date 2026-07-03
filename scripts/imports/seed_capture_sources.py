"""Seed CAPTURE_SOURCE with the four approved MVP data sources (D-005, D-022, D-049).

Trust tier integer: lower = higher trust (1=Verified is most trusted).

Usage:
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/imports/seed_capture_sources.py

Idempotent: uses INSERT ... ON CONFLICT (source_type) DO NOTHING.
"""

from __future__ import annotations

import os
import sys

from _utils import normalize_db_url
from sqlalchemy import create_engine, text

# Static trust tiers per D-049: Verified > Tracer > LinkedIn > Alumni Form.
# Alumni Form is deferred (D-005) but the source row must exist for FK integrity.
CAPTURE_SOURCES: list[dict[str, object]] = [
    {"source_type": "Verified Faculty Record", "trust_tier": 1},
    {"source_type": "Tracer Study", "trust_tier": 2},
    {"source_type": "LinkedIn", "trust_tier": 3},
    {"source_type": "Alumni Form", "trust_tier": 4},
]

# RETURNING 1 lets us count actual inserts; rows skipped by ON CONFLICT return nothing.
# conn.execute(text, list) routes to executemany whose rowcount is undefined in psycopg v3.
_INSERT_SQL = text("""
    INSERT INTO capture_source (source_type, trust_tier)
    VALUES (:source_type, :trust_tier)
    ON CONFLICT (source_type) DO NOTHING
    RETURNING 1
    """)


def seed(database_url: str) -> None:
    engine = create_engine(normalize_db_url(database_url), future=True)
    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, CAPTURE_SOURCES)
        inserted = len(result.fetchall())
    print(f"seed_capture_sources: {inserted} row(s) inserted (0 = already seeded).")


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    seed(url)


if __name__ == "__main__":
    main()
