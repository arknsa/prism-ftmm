"""Location normalization service (P3.8).

Resolves a raw location string from a staged row to a canonical LOCATION row
per the algorithm defined in Artifact A3 (docs/decisions/GEOGRAPHIC_CANONICAL_SPEC.md).

Algorithm summary:
  1. Blank/absent → return None.
  2. Remote sentinel keywords → return seeded Remote row.
  3. Tokenize, extract country, match city/province against seeded rows.
  4. First-sight: create a new LOCATION row with best-effort fields.

Design constraints:
- Deterministic only (D-039). No fuzzy matching, no geocoding API.
- First-sight creation is acceptable; curators merge duplicates in Phase 4.
- All writes go through the caller's session; caller owns commit (D-031 pattern).
- country defaults to "Indonesia" when no known country token is found (A3 §3a).

Decisions: D-019, D-031, D-039, Artifact A3.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference import Location

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Remote sentinel keywords (A3 §2)
# ---------------------------------------------------------------------------

_REMOTE_KEYWORDS: frozenset[str] = frozenset({"remote", "wfh", "work from home", "work-from-home"})

# ---------------------------------------------------------------------------
# Known country token map: token (lowercase) → canonical country name (A3 §5)
# Order matters for multi-word tokens checked before single-word tokens.
# ---------------------------------------------------------------------------

_COUNTRY_TOKENS: dict[str, str] = {
    # multi-word first
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "south korea": "South Korea",
    "work from home": "Remote",
    # single-word
    "indonesia": "Indonesia",
    "id": "Indonesia",
    "singapore": "Singapore",
    "sg": "Singapore",
    "malaysia": "Malaysia",
    "my": "Malaysia",
    "usa": "United States",
    "us": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "england": "United Kingdom",
    "australia": "Australia",
    "au": "Australia",
    "japan": "Japan",
    "jp": "Japan",
    "korea": "South Korea",
    "kr": "South Korea",
    "netherlands": "Netherlands",
    "holland": "Netherlands",
    "nl": "Netherlands",
    "germany": "Germany",
    "de": "Germany",
}

_DEFAULT_COUNTRY = "Indonesia"

# Province-name substrings used to detect the last token as a province name.
_PROVINCE_HINTS: frozenset[str] = frozenset(
    {"java", "sumatra", "sulawesi", "kalimantan", "bali", "papua"}
)


def resolve_location(
    raw_location: str | None,
    session: Session,
) -> Location | None:
    """Resolve a raw location string to a canonical LOCATION row.

    Returns None when the input is blank/absent (A3 §1). Otherwise always
    returns a LOCATION row — either an existing seeded/prior row or a
    newly created first-sight row (A3 §3c).

    The caller's session is used; the caller owns flush/commit.

    Args:
        raw_location: free-form location text from the staged row (may be None).
        session: active SQLAlchemy session.

    Returns:
        A Location instance or None.
    """
    # Step 1 — blank/absent
    if not raw_location or not raw_location.strip():
        return None

    text = raw_location.strip()
    lower = text.lower()

    # Step 2 — remote sentinel
    if any(kw in lower for kw in _REMOTE_KEYWORDS):
        remote = _get_remote_sentinel(session)
        return remote

    # Step 3 — parse tokens, extract country, match city/province
    country, candidate_tokens = _extract_country(text)
    location = _match_location(country, candidate_tokens, session)
    return location


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_remote_sentinel(session: Session) -> Location:
    """Return the seeded Remote LOCATION sentinel row, creating it if absent."""
    row = session.scalar(select(Location).where(Location.country == "Remote"))
    if row is not None:
        return row
    row = Location(country="Remote", province=None, city=None, region="Remote")
    session.add(row)
    session.flush()
    logger.warning("location_normalization: Remote sentinel row not seeded — created on demand")
    return row


def _extract_country(text: str) -> tuple[str, list[str]]:
    """Extract a country from the raw text and return (country, remaining_tokens).

    Tries multi-word country tokens first (e.g. "United States") then single-word.
    Remaining tokens (after removing the country token) are candidate city/province.
    Country defaults to Indonesia if no known token is found.
    """
    # Split by comma and whitespace, strip each piece
    parts = [p.strip() for p in re.split(r"[,\s]+", text) if p.strip()]

    # Check multi-word tokens first by scanning the full lowercase text
    lower = text.lower()
    multi_word_countries = [(k, v) for k, v in _COUNTRY_TOKENS.items() if " " in k or "-" in k]
    for token, canonical in multi_word_countries:
        if token in lower:
            remaining = [p for p in parts if p.lower() not in token.split() and p.lower() != token]
            return canonical, remaining

    # Single-word token matching
    matched_country: str | None = None
    matched_idx: int = -1
    for idx, part in enumerate(parts):
        lp = part.lower()
        if lp in _COUNTRY_TOKENS:
            matched_country = _COUNTRY_TOKENS[lp]
            matched_idx = idx
            break

    if matched_country is not None:
        remaining = [p for i, p in enumerate(parts) if i != matched_idx]
        return matched_country, remaining

    # No country token found — default to Indonesia (A3 §3a)
    return _DEFAULT_COUNTRY, parts


def _match_location(
    country: str,
    candidate_tokens: list[str],
    session: Session,
) -> Location:
    """Match city/province tokens against existing LOCATION rows or create first-sight.

    Priority:
    1. Exact city match in DB (same country).
    2. Exact province match in DB (same country).
    3. First-sight creation with country + best-effort city/province.
    """
    # Title-case candidates for matching
    title_tokens = [t.title() for t in candidate_tokens]

    # 1. Try exact city match
    for token in title_tokens:
        row = session.scalar(
            select(Location).where(
                Location.country == country,
                Location.city == token,
            )
        )
        if row is not None:
            return row

    # 2. Try exact province match
    for token in title_tokens:
        row = session.scalar(
            select(Location).where(
                Location.country == country,
                Location.province == token,
                Location.city.is_(None),
            )
        )
        if row is not None:
            return row

    # 3. First-sight creation (A3 §3c)
    city: str | None = title_tokens[0] if title_tokens else None
    province: str | None = title_tokens[1] if len(title_tokens) > 1 else None

    # For Indonesian locations try province heuristics: if second token looks like
    # a known province prefix ("Java", "Sumatra", "Sulawesi", "Kalimantan", "Bali")
    # treat it as province and first token as city; otherwise assign by position.
    if country == "Indonesia" and len(title_tokens) >= 2:
        last_lower = title_tokens[-1].lower()
        if any(hint in last_lower for hint in _PROVINCE_HINTS):
            province = title_tokens[-1]
            city = title_tokens[0] if len(title_tokens) > 1 else None

    new_row = Location(
        country=country,
        province=province,
        city=city,
        region=None,
    )
    session.add(new_row)
    session.flush()
    logger.info(
        "location_normalization: first-sight row created country=%r province=%r city=%r",
        country,
        province,
        city,
    )
    return new_row
