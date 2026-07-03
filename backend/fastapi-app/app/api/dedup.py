"""Dedup curator review queue endpoints (P4.3).

Implements the curator workflow for Tier-2 dedup candidates:

  GET  /api/v1/dedup/candidates          — list pending candidates
  GET  /api/v1/dedup/candidates/{id}     — single candidate detail
  POST /api/v1/dedup/candidates/{id}/resolve  — merge or keep-separate

Permission required: dedup:review (Data Curator, Admin).

Audit: every resolution writes an AUDIT_LOG entry (D-025).

Decisions: D-024 (curator gate), D-025 (audit), D-031 (gateway), D-045 (no auto-merge).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.schemas.auth import AuthenticatedUser
from app.schemas.dedup import DedupCandidateListOut, DedupCandidateOut, DedupResolveIn
from app.services.audit import write_audit_entry
from app.services.dedup_queue import (
    get_candidate,
    get_pending_candidates,
    resolve_candidate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dedup", tags=["dedup"])


# ---------------------------------------------------------------------------
# GET /api/v1/dedup/candidates
# ---------------------------------------------------------------------------


@router.get(
    "/candidates",
    response_model=DedupCandidateListOut,
    summary="List pending dedup candidates awaiting curator review",
)
def list_pending_candidates(
    _user: AuthenticatedUser = Depends(require_permission("dedup:review")),
    session: Session = Depends(get_session),
) -> DedupCandidateListOut:
    """Return all dedup candidate queue entries with resolution='pending'.

    Permission required: ``dedup:review`` (Admin, Data Curator).
    """
    candidates = get_pending_candidates(session)
    return DedupCandidateListOut(
        total=len(candidates),
        items=[DedupCandidateOut.model_validate(c) for c in candidates],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/dedup/candidates/{candidate_id}
# ---------------------------------------------------------------------------


@router.get(
    "/candidates/{candidate_id}",
    response_model=DedupCandidateOut,
    summary="Get a single dedup candidate by ID",
)
def get_dedup_candidate(
    candidate_id: int,
    _user: AuthenticatedUser = Depends(require_permission("dedup:review")),
    session: Session = Depends(get_session),
) -> DedupCandidateOut:
    """Return a single dedup candidate queue entry.

    Permission required: ``dedup:review``.
    """
    candidate = get_candidate(candidate_id, session)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dedup candidate {candidate_id} not found.",
        )
    return DedupCandidateOut.model_validate(candidate)


# ---------------------------------------------------------------------------
# POST /api/v1/dedup/candidates/{candidate_id}/resolve
# ---------------------------------------------------------------------------


@router.post(
    "/candidates/{candidate_id}/resolve",
    response_model=DedupCandidateOut,
    summary="Resolve a dedup candidate: merge or keep-separate",
)
def resolve_dedup_candidate(
    candidate_id: int,
    body: DedupResolveIn,
    user: AuthenticatedUser = Depends(require_permission("dedup:review")),
    session: Session = Depends(get_session),
) -> DedupCandidateOut:
    """Curator resolves a pending dedup candidate as 'merge' or 'keep_separate'.

    - ``merge``: the staged row belongs to the same real person as the matched alumni.
    - ``keep_separate``: the staged row represents a distinct person.

    Writes an audit entry and commits the resolution atomically.
    Permission required: ``dedup:review`` (Admin, Data Curator).
    """
    try:
        old_resolution = "pending"
        candidate = resolve_candidate(
            candidate_id=candidate_id,
            resolution=body.resolution,
            resolved_by=user.user_id,
            session=session,
        )

        write_audit_entry(
            session,
            table_name="dedup_candidate",
            record_id=str(candidate_id),
            action_type="UPDATE",
            old_values={"resolution": old_resolution},
            new_values={
                "resolution": candidate.resolution,
                "resolved_by": candidate.resolved_by,
            },
            changed_by=user.user_id,
        )

        session.commit()

    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        session.rollback()
        logger.exception("Unexpected error resolving dedup candidate %d", candidate_id)
        raise

    logger.info(
        "dedup resolved: candidate_id=%d resolution=%r actor=%d",
        candidate_id,
        candidate.resolution,
        user.user_id,
    )
    return DedupCandidateOut.model_validate(candidate)
