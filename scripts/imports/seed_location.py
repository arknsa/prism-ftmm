"""Seed LOCATION with Indonesian provinces/cities and catch-all entries (D-018, D-019).

Idempotency: checks for an existing row matching (country, province, city) before
inserting. The LOCATION table has no composite unique DB constraint (locations are
intentionally extensible by curators), so we guard in application logic here.

Usage:
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/imports/seed_location.py
"""

from __future__ import annotations

import os
import sys
from typing import Any

from _utils import normalize_db_url
from sqlalchemy import create_engine, text

# Type alias for a location row (all values are str or None).
LocationRow = dict[str, Any]


# Indonesia-focused initial set.
# country / province / city / region (region is a broad descriptor; may be NULL).
# Key provinces and at least one major city per province are included.
LOCATIONS: list[LocationRow] = [
    # --- East Java (Jawa Timur) ---
    {
        "country": "Indonesia",
        "province": "East Java",
        "city": "Surabaya",
        "region": None,
    },
    {"country": "Indonesia", "province": "East Java", "city": "Malang", "region": None},
    {
        "country": "Indonesia",
        "province": "East Java",
        "city": "Sidoarjo",
        "region": None,
    },
    {"country": "Indonesia", "province": "East Java", "city": "Gresik", "region": None},
    # --- DKI Jakarta ---
    {
        "country": "Indonesia",
        "province": "DKI Jakarta",
        "city": "Jakarta",
        "region": None,
    },
    # --- West Java (Jawa Barat) ---
    {
        "country": "Indonesia",
        "province": "West Java",
        "city": "Bandung",
        "region": None,
    },
    {"country": "Indonesia", "province": "West Java", "city": "Bekasi", "region": None},
    {"country": "Indonesia", "province": "West Java", "city": "Depok", "region": None},
    # --- Banten ---
    {"country": "Indonesia", "province": "Banten", "city": "Tangerang", "region": None},
    # --- Central Java (Jawa Tengah) ---
    {
        "country": "Indonesia",
        "province": "Central Java",
        "city": "Semarang",
        "region": None,
    },
    {
        "country": "Indonesia",
        "province": "Central Java",
        "city": "Solo",
        "region": None,
    },
    # --- DI Yogyakarta ---
    {
        "country": "Indonesia",
        "province": "DI Yogyakarta",
        "city": "Yogyakarta",
        "region": None,
    },
    # --- Bali ---
    {"country": "Indonesia", "province": "Bali", "city": "Denpasar", "region": None},
    # --- South Sulawesi (Sulawesi Selatan) ---
    {
        "country": "Indonesia",
        "province": "South Sulawesi",
        "city": "Makassar",
        "region": None,
    },
    # --- North Sumatra (Sumatera Utara) ---
    {
        "country": "Indonesia",
        "province": "North Sumatra",
        "city": "Medan",
        "region": None,
    },
    # --- South Sumatra (Sumatera Selatan) ---
    {
        "country": "Indonesia",
        "province": "South Sumatra",
        "city": "Palembang",
        "region": None,
    },
    # --- Riau ---
    {"country": "Indonesia", "province": "Riau", "city": "Pekanbaru", "region": None},
    # --- Province-level only (city unknown) ---
    {"country": "Indonesia", "province": "East Java", "city": None, "region": None},
    {"country": "Indonesia", "province": "DKI Jakarta", "city": None, "region": None},
    # --- Catch-alls ---
    # Remote workers — no geographic affiliation.
    {"country": "Remote", "province": None, "city": None, "region": "Remote"},
    # International / overseas alumni outside Indonesia.
    {"country": "Other", "province": None, "city": None, "region": "International"},
]

_CHECK_SQL = text("""
    SELECT 1 FROM location
    WHERE country = :country
      AND (province IS NOT DISTINCT FROM :province)
      AND (city IS NOT DISTINCT FROM :city)
    LIMIT 1
    """)

_INSERT_SQL = text("""
    INSERT INTO location (country, province, city, region)
    VALUES (:country, :province, :city, :region)
    """)


def seed(database_url: str) -> None:
    engine = create_engine(normalize_db_url(database_url), future=True)
    inserted = 0
    skipped = 0
    with engine.begin() as conn:
        for row in LOCATIONS:
            exists = conn.execute(_CHECK_SQL, row).scalar()
            if exists:
                skipped += 1
            else:
                conn.execute(_INSERT_SQL, row)
                inserted += 1
    print(
        f"seed_location: {inserted} row(s) inserted, {skipped} skipped (already seeded)."
    )


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    seed(url)


if __name__ == "__main__":
    main()
