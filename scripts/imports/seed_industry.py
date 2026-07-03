"""Seed INDUSTRY with the initial taxonomy (D-009, D-010, D-042).

21 rows covering sectors relevant to FTMM's five programs and the Indonesian job market.
'Other / Unclassified' catch-all is required for normalization completeness.

Usage:
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/imports/seed_industry.py

Idempotent: ON CONFLICT (industry_name) DO NOTHING.
"""

from __future__ import annotations

import os
import sys

from _utils import normalize_db_url
from sqlalchemy import create_engine, text

# industry_name is granular; sector_name is the parent grouping (D-042).
# Chosen to reflect FTMM programs (Data Science, Industrial Engineering,
# Electrical Engineering, Nanotechnology, Robotics) and Indonesian job market.
INDUSTRIES: list[dict[str, str]] = [
    # Technology
    {"industry_name": "Software Development", "sector_name": "Technology"},
    {"industry_name": "Data & Analytics", "sector_name": "Technology"},
    {
        "industry_name": "Artificial Intelligence & Machine Learning",
        "sector_name": "Technology",
    },
    {"industry_name": "Cybersecurity", "sector_name": "Technology"},
    {"industry_name": "Cloud & Infrastructure", "sector_name": "Technology"},
    {"industry_name": "Telecommunications", "sector_name": "Technology"},
    # Manufacturing & Engineering
    {
        "industry_name": "Electronics Manufacturing",
        "sector_name": "Manufacturing & Engineering",
    },
    {
        "industry_name": "Industrial Automation",
        "sector_name": "Manufacturing & Engineering",
    },
    {
        "industry_name": "Nanotechnology & Advanced Materials",
        "sector_name": "Manufacturing & Engineering",
    },
    {
        "industry_name": "Robotics & Automation",
        "sector_name": "Manufacturing & Engineering",
    },
    # Energy & Resources
    {"industry_name": "Oil & Gas", "sector_name": "Energy & Resources"},
    {"industry_name": "Renewable Energy", "sector_name": "Energy & Resources"},
    {"industry_name": "Mining & Metals", "sector_name": "Energy & Resources"},
    # Finance
    {"industry_name": "Banking & Financial Services", "sector_name": "Finance"},
    {"industry_name": "Insurance", "sector_name": "Finance"},
    # Professional Services
    {"industry_name": "Consulting", "sector_name": "Professional Services"},
    # Education & Research
    {"industry_name": "Research & Development", "sector_name": "Education & Research"},
    {"industry_name": "Higher Education", "sector_name": "Education & Research"},
    # Public Sector
    {"industry_name": "Government & Public Sector", "sector_name": "Public Sector"},
    # Healthcare
    {"industry_name": "Healthcare", "sector_name": "Healthcare"},
    # Catch-all — required for normalization completeness
    {"industry_name": "Other / Unclassified", "sector_name": "Other"},
]

# RETURNING 1 lets us count actual inserts; rows skipped by ON CONFLICT return nothing.
# conn.execute(text, list) routes to executemany whose rowcount is undefined in psycopg v3.
_INSERT_SQL = text("""
    INSERT INTO industry (industry_name, sector_name)
    VALUES (:industry_name, :sector_name)
    ON CONFLICT (industry_name) DO NOTHING
    RETURNING 1
    """)


def seed(database_url: str) -> None:
    engine = create_engine(normalize_db_url(database_url), future=True)
    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, INDUSTRIES)
        inserted = len(result.fetchall())
    print(f"seed_industry: {inserted} row(s) inserted (0 = already seeded).")


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    seed(url)


if __name__ == "__main__":
    main()
