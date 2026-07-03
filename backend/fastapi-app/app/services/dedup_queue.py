"""Dedup queue management service (P4.3).

Provides operations for the curator review queue:

  enqueue_candidate(staging_row_id, matched_alumni_id, session)
      → DedupCandidate
  resolve_merge(candidate_id, resolved_by, session)
      → DedupCandidate   (resolution="merge")
  resolve_keep_separate(candidate_id, resolved_by, session)
      → DedupCandidate   (resolution="keep_separate")
  get_pending_candidates(session)
      → list[DedupCandidate]

Design constraints (D-024, D-039, D-045, D-031):
- Only the curator can resolve candidates (D-024).
- No auto-merge for Tier-2 candidates — every match requires human decision (D-045).
- The caller owns commit; this service only adds/updates within the session (D-031).

Decisions: D-024, D-031, D-039, D-044, D-045.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dedup import DedupCandidate

_VALID_RESOLUTIONS: frozenset[str] = frozenset({"merge", "keep_separate"})


def enqueue_candidate(
    staging_row_id: int,
    matched_alumni_id: int,
    session: Session,
) -> DedupCandidate:
    """Create a DedupCandidate queue entry for a Tier-2 match needing curator review.

    This function adds the entry to the session but does NOT flush or commit.
    If an identical (staging_row_id, matched_alumni_id) entry already exists
    (pending), it is returned as-is to avoid duplicate queue entries.

    Args:
        staging_row_id: FK to the staged row that triggered the Tier-2 match.
        matched_alumni_id: FK to the existing Alumni that matched the candidate key.
        session: active SQLAlchemy session — caller owns commit.

    Returns:
        The DedupCandidate instance (added to session, not yet committed).
    """
    existing = session.scalar(
        select(DedupCandidate).where(
            DedupCandidate.staging_row_id == staging_row_id,
            DedupCandidate.matched_alumni_id == matched_alumni_id,
            DedupCandidate.resolution == "pending",
        )
    )
    if existing is not None:
        return existing

    candidate = DedupCandidate(
        staging_row_id=staging_row_id,
        matched_alumni_id=matched_alumni_id,
        resolution="pending",
    )
    session.add(candidate)
    return candidate


def resolve_candidate(
    candidate_id: int,
    resolution: str,
    resolved_by: int,
    session: Session,
) -> DedupCandidate:
    """Resolve a pending DedupCandidate with a curator decision.

    Args:
        candidate_id: PK of the DedupCandidate to resolve.
        resolution: "merge" or "keep_separate".
        resolved_by: AppUser.user_id of the curator making the decision.
        session: active SQLAlchemy session — caller owns commit.

    Returns:
        The updated DedupCandidate.

    Raises:
        ValueError: candidate not found, already resolved, or invalid resolution.
    """
    if resolution not in _VALID_RESOLUTIONS:
        raise ValueError(
            f"Invalid resolution {resolution!r}. Must be one of: {sorted(_VALID_RESOLUTIONS)}"
        )

    candidate = session.get(DedupCandidate, candidate_id)
    if candidate is None:
        raise ValueError(f"DedupCandidate {candidate_id} not found.")
    if candidate.resolution != "pending":
        raise ValueError(
            f"DedupCandidate {candidate_id} is already resolved: {candidate.resolution!r}."
        )

    candidate.resolution = resolution
    candidate.resolved_by = resolved_by
    candidate.resolved_at = datetime.datetime.now(datetime.UTC)
    return candidate


def get_pending_candidates(session: Session) -> list[DedupCandidate]:
    """Return all DedupCandidate rows with resolution='pending', ordered by id.

    Args:
        session: active SQLAlchemy session (read-only).

    Returns:
        List of pending DedupCandidate rows (may be empty).
    """
    return list(
        session.scalars(
            select(DedupCandidate)
            .where(DedupCandidate.resolution == "pending")
            .order_by(DedupCandidate.dedup_candidate_id)
        ).all()
    )


def get_candidate(candidate_id: int, session: Session) -> DedupCandidate | None:
    """Return a single DedupCandidate by PK, or None if not found."""
    return session.get(DedupCandidate, candidate_id)
