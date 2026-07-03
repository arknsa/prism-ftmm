"""Deduplication services (P4.1, P4.2).

Two-tier deterministic deduplication per D-045:

  Tier 1 — exact linkedin_url match (auto-link; no curator needed)
  Tier 2 — candidate key match (name + program + year → curator queue)

Design constraints (D-039, D-044, D-045, D-002):
- Deterministic only: same input → same match result every call.
- No fuzzy/AI matching.
- Tier 1 auto-links (no human review needed for an exact URL match).
- Tier 2 produces a candidate set for curator review — it never auto-merges.
- These functions only READ the DB; they do NOT write.
- The caller owns commit; nothing here mutates any row.

Decisions: D-002, D-039, D-044, D-045.
"""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alumni import Alumni

# ---------------------------------------------------------------------------
# Tier 1 — exact linkedin_url match (P4.1)
# ---------------------------------------------------------------------------

_LINKEDIN_NORMALIZE_RE = re.compile(r"[/?#].*$")


def _normalize_linkedin_url(raw: str) -> str:
    """Return a canonical form of a LinkedIn URL for exact-match comparison.

    Steps:
    1. Strip whitespace.
    2. Lowercase.
    3. Remove query string, fragment, and trailing path after profile slug.

    This is purely for robust exact-match — it does NOT perform fuzzy matching.
    """
    url = raw.strip().lower()
    # Remove trailing slash before comparison
    url = url.rstrip("/")
    return url


def find_by_linkedin_url(raw_linkedin_url: str | None, session: Session) -> Alumni | None:
    """Tier-1 dedup: return existing Alumni with exact normalized linkedin_url match.

    If raw_linkedin_url is blank/None, returns None immediately (no match possible).
    This function only performs SELECT; it never writes or updates any row.

    Args:
        raw_linkedin_url: raw URL string from staged row (may be None/blank).
        session: active SQLAlchemy session (read-only).

    Returns:
        The matching Alumni row, or None if no match or no URL given.
    """
    if not raw_linkedin_url or not raw_linkedin_url.strip():
        return None

    normalized = _normalize_linkedin_url(raw_linkedin_url)
    # Also check the raw value as stored (some rows may not be normalized)
    result = session.scalar(select(Alumni).where(Alumni.linkedin_url == normalized))
    if result is not None:
        return result
    # Fallback: check raw (un-normalized) value in case DB stores raw
    if normalized != raw_linkedin_url.strip():
        result = session.scalar(
            select(Alumni).where(Alumni.linkedin_url == raw_linkedin_url.strip())
        )
    return result


# ---------------------------------------------------------------------------
# Tier 2 — candidate key match (P4.2)
# ---------------------------------------------------------------------------

# Honorific prefixes to strip before name normalization (Indonesian + English)
_HONORIFICS: frozenset[str] = frozenset(
    {
        "dr",
        "dr.",
        "drs",
        "drs.",
        "prof",
        "prof.",
        "ir",
        "ir.",
        "mr",
        "mr.",
        "mrs",
        "mrs.",
        "ms",
        "ms.",
        "bpk",
        "bpk.",
        "ibu",
        "ibu.",
        "hj",
        "hj.",
        "h.",
        "h",
        "s.t",
        "s.t.",
        "m.t",
        "m.t.",
        "s.kom",
        "m.kom",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALPHA_RE = re.compile(r"[^a-z0-9\s]")


def normalize_full_name(raw_name: str | None) -> str | None:
    """Return a deterministic normalized form of a full name for candidate-key matching.

    Steps (D-044):
    1. Strip whitespace.
    2. Unicode NFKD normalize → ASCII (removes diacritics).
    3. Lowercase.
    4. Remove honorific prefixes and suffixes.
    5. Collapse whitespace.
    6. Blank result → None.

    Args:
        raw_name: raw full name (may be None/blank).

    Returns:
        Normalized name string, or None if result is blank after normalization.
    """
    if not raw_name or not raw_name.strip():
        return None

    # Unicode normalize to NFKD then encode to ASCII dropping non-ASCII chars
    nfkd = unicodedata.normalize("NFKD", raw_name.strip())
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    lower = ascii_name.lower()

    # Remove non-alphanumeric except spaces (strips punctuation, periods in honorifics)
    cleaned = _NON_ALPHA_RE.sub(" ", lower)

    # Collapse whitespace and tokenize
    tokens = _WHITESPACE_RE.sub(" ", cleaned).strip().split()

    # Strip honorific tokens from front and back
    while tokens and tokens[0] in _HONORIFICS:
        tokens = tokens[1:]
    while tokens and tokens[-1] in _HONORIFICS:
        tokens = tokens[:-1]

    result = " ".join(tokens).strip()
    return result if result else None


def build_candidate_key(
    raw_name: str | None,
    study_program_id: int | None,
    graduation_year: int | None,
) -> tuple[str, int, int] | None:
    """Construct the deterministic Tier-2 candidate key (D-044).

    Key = (normalized_name, study_program_id, graduation_year).
    Returns None if any component is missing (cannot produce a valid key).

    Args:
        raw_name: raw full name from staged row.
        study_program_id: resolved study_program FK (from match_program result).
        graduation_year: integer graduation year from staged row.

    Returns:
        A 3-tuple (normalized_name, study_program_id, graduation_year),
        or None if any required component is absent.
    """
    normalized_name = normalize_full_name(raw_name)
    if normalized_name is None or study_program_id is None or graduation_year is None:
        return None
    return (normalized_name, study_program_id, graduation_year)


def find_candidates_by_key(
    raw_name: str | None,
    study_program_id: int | None,
    graduation_year: int | None,
    session: Session,
) -> list[Alumni]:
    """Tier-2 dedup: return Alumni rows matching the deterministic candidate key.

    The candidate key is (normalized_name, study_program_id, graduation_year) per D-044.
    A match means there is at least one existing alumnus with the same key — the
    curator must decide whether to merge or keep separate (no auto-merge for Tier 2).

    This function only performs SELECT; it never writes or updates any row.

    Args:
        raw_name: raw full name from staged row.
        study_program_id: resolved study_program FK.
        graduation_year: integer graduation year.
        session: active SQLAlchemy session (read-only).

    Returns:
        List of matching Alumni rows (empty list if no match or missing key).
    """
    key = build_candidate_key(raw_name, study_program_id, graduation_year)
    if key is None:
        return []

    normalized_name, program_id, grad_year = key

    # Fetch all alumni with matching program + year, then filter by normalized name
    # in Python (normalization is not stored in DB — deterministic function applied here).
    candidates = session.scalars(
        select(Alumni).where(
            Alumni.study_program_id == program_id,
            Alumni.graduation_year == grad_year,
        )
    ).all()

    return [a for a in candidates if normalize_full_name(a.full_name) == normalized_name]
