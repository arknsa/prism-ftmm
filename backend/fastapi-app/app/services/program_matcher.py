"""Program/university matcher service (P3.4).

Implements deterministic matching per Artifact A6 (PROGRAM_VARIANT_MAP_SPEC.md):

  match_program(raw_program, session) -> StudyProgram
  is_unair(raw_university)            -> bool

Design constraints (D-003, D-004, D-024, D-040, D-039, D-002):
- Deterministic: same input → same StudyProgram every call (no fuzzy/AI).
- Anything not in the variant map → "Other / Unknown" sentinel (is_ftmm_valid=False).
- University is an explicit string match on a small set of recognized variants.
- These functions only READ the DB (study_program table); they do NOT write.
- The caller owns commit; match_program never modifies any row.

Decisions: D-003, D-004, D-024, D-039, D-040, D-002, Artifact A6.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference import StudyProgram

# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------


def _normalize(raw: str) -> str:
    """Lowercase and collapse whitespace for deterministic key comparison."""
    return re.sub(r"\s+", " ", raw.strip().lower())


# ---------------------------------------------------------------------------
# Program variant map (Artifact A6 §3)
# Keys: normalized variant string → canonical program_name (matches seed_study_programs.py)
# ---------------------------------------------------------------------------

_PROGRAM_VARIANT_MAP: dict[str, str] = {
    # Technology of Data Science
    "technology of data science": "Technology of Data Science",
    "teknologi sains data": "Technology of Data Science",
    "data science": "Technology of Data Science",
    "data science technology": "Technology of Data Science",
    "tech data science": "Technology of Data Science",
    "tsd": "Technology of Data Science",
    "data science tech": "Technology of Data Science",
    "sains data teknologi": "Technology of Data Science",
    "teknik data": "Technology of Data Science",
    # Industrial Engineering
    "industrial engineering": "Industrial Engineering",
    "teknik industri": "Industrial Engineering",
    "industrial eng": "Industrial Engineering",
    "ie": "Industrial Engineering",
    "ti": "Industrial Engineering",
    "industri": "Industrial Engineering",
    "industrial": "Industrial Engineering",
    "teknik industri (s1)": "Industrial Engineering",
    # Electrical Engineering
    "electrical engineering": "Electrical Engineering",
    "teknik elektro": "Electrical Engineering",
    "electrical eng": "Electrical Engineering",
    "ee": "Electrical Engineering",
    "te": "Electrical Engineering",
    "elektro": "Electrical Engineering",
    "teknik ketenagalistrikan": "Electrical Engineering",
    "electrical": "Electrical Engineering",
    # Nanotechnology Engineering
    "nanotechnology engineering": "Nanotechnology Engineering",
    "teknik nanoteknologi": "Nanotechnology Engineering",
    "nanotechnology eng": "Nanotechnology Engineering",
    "nano": "Nanotechnology Engineering",
    "nanoteknologi": "Nanotechnology Engineering",
    "teknik nano": "Nanotechnology Engineering",
    "nte": "Nanotechnology Engineering",
    "nanotechnology": "Nanotechnology Engineering",
    # Robotics and Artificial Intelligence Engineering
    "robotics and artificial intelligence engineering": (
        "Robotics and Artificial Intelligence Engineering"
    ),
    "teknik robotika dan kecerdasan buatan": "Robotics and Artificial Intelligence Engineering",
    "robotics ai": "Robotics and Artificial Intelligence Engineering",
    "robotics & ai": "Robotics and Artificial Intelligence Engineering",
    "robotics and ai engineering": "Robotics and Artificial Intelligence Engineering",
    "rai": "Robotics and Artificial Intelligence Engineering",
    "robotika": "Robotics and Artificial Intelligence Engineering",
    "kecerdasan buatan": "Robotics and Artificial Intelligence Engineering",
    "robotics": "Robotics and Artificial Intelligence Engineering",
    "ai engineering": "Robotics and Artificial Intelligence Engineering",
    "trkb": "Robotics and Artificial Intelligence Engineering",
    "teknik robot": "Robotics and Artificial Intelligence Engineering",
    "robotics engineering": "Robotics and Artificial Intelligence Engineering",
}

_SENTINEL_NAME = "Other / Unknown"

# ---------------------------------------------------------------------------
# University variants (Artifact A6 §4)
# ---------------------------------------------------------------------------

_UNAIR_VARIANTS: frozenset[str] = frozenset(
    {
        "universitas airlangga",
        "unair",
        "ua",
        "airlangga university",
        "airlangga",
    }
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def match_program(raw_program: str | None, session: Session) -> StudyProgram:
    """Resolve a raw program string to a canonical StudyProgram row.

    Algorithm (Artifact A6 §6):
    1. Normalize: lowercase, strip, collapse whitespace.
    2. Look up in PROGRAM_VARIANT_MAP.
    3. If found: fetch the matching StudyProgram by program_name from DB.
    4. If not found: fetch the sentinel row ("Other / Unknown", is_ftmm_valid=False).

    Args:
        raw_program: raw study program text from staged row (may be None/blank).
        session: active SQLAlchemy session (read-only; no writes performed here).

    Returns:
        A StudyProgram instance — either the matched program or the sentinel.

    Raises:
        RuntimeError if the sentinel row is missing from the DB (seed not run).
    """
    canonical_name: str

    if not raw_program or not raw_program.strip():
        canonical_name = _SENTINEL_NAME
    else:
        key = _normalize(raw_program)
        canonical_name = _PROGRAM_VARIANT_MAP.get(key, _SENTINEL_NAME)

    program = session.scalar(
        select(StudyProgram).where(StudyProgram.program_name == canonical_name)
    )
    if program is None:
        if canonical_name == _SENTINEL_NAME:
            raise RuntimeError(
                "Sentinel study program 'Other / Unknown' not found in DB. "
                "Run seed_study_programs.py before using match_program()."
            )
        # Fallback: try to get sentinel instead
        program = session.scalar(
            select(StudyProgram).where(StudyProgram.program_name == _SENTINEL_NAME)
        )
        if program is None:
            raise RuntimeError(
                f"Study program '{canonical_name}' not found in DB and sentinel is also missing. "
                "Run seed_study_programs.py."
            )
    return program


def is_unair(raw_university: str | None) -> bool:
    """Return True if raw_university matches a recognized Universitas Airlangga variant.

    Matching is case-insensitive and whitespace-normalized (Artifact A6 §4).
    Any unrecognized string (including None/blank) → False.

    Args:
        raw_university: raw university text from staged row (may be None/blank).

    Returns:
        True if the string is a recognized UNAIR variant; False otherwise.
    """
    if not raw_university or not raw_university.strip():
        return False
    return _normalize(raw_university) in _UNAIR_VARIANTS
