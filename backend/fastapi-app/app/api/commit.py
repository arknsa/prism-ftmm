"""Commit and validation endpoints (P4.5).

  POST /api/v1/commit              — commit all pending rows in a batch to Alumni + CareerRecord
  POST /api/v1/alumni/{id}/validate — curator validates or rejects an alumni record (D-024)
  GET  /api/v1/alumni/{id}         — read an alumni record

Permission required: import:run (batch commit), alumni:validate (validate/reject).

Decisions: D-020, D-024, D-025, D-031, D-045, D-047.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.models.alumni import Alumni, ValidationStatus
from app.schemas.auth import AuthenticatedUser
from app.schemas.commit import (
    CommitBatchIn,
    CommitBatchResultOut,
    CommitRowResultOut,
    ValidateAlumniIn,
)
from app.services.audit import write_audit_entry
from app.services.commit import CommitOutcome, commit_batch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["commit"])

_VALID_VALIDATE_ACTIONS = frozenset({"validate", "reject"})


# ---------------------------------------------------------------------------
# POST /api/v1/commit
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/commit",
    response_model=CommitBatchResultOut,
    summary="Commit a staged import batch to Alumni + CareerRecord tables",
)
def commit_import_batch(
    body: CommitBatchIn,
    user: AuthenticatedUser = Depends(require_permission("import:run")),
    session: Session = Depends(get_session),
) -> CommitBatchResultOut:
    """Process all pending StagingRows in a batch through the full normalization pipeline.

    For each row:
    - Runs program matching, company resolution, role/seniority normalization.
    - Dedup Tier-1 (exact linkedin_url) and Tier-2 (name+program+year).
    - Creates Alumni and CareerRecord rows; enforces D-020 (one is_current per alumni).
    - Writes audit entries for every INSERT.
    - Returns per-row outcomes including pending_dedup rows needing curator action.

    Permission required: ``import:run`` (Admin, Data Curator).
    """
    try:
        results = commit_batch(
            batch_id=body.batch_id,
            snapshot_id=body.snapshot_id,
            actor_id=user.user_id,
            session=session,
        )

        write_audit_entry(
            session,
            table_name="import_batch",
            record_id=str(body.batch_id),
            action_type="UPDATE",
            new_values={
                "committed_to_snapshot": body.snapshot_id,
                "committed_by": user.user_id,
            },
            changed_by=user.user_id,
        )

        session.commit()

    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        logger.exception("Unexpected error committing batch %d", body.batch_id)
        raise

    row_outs = [
        CommitRowResultOut(
            staging_row_id=r.staging_row_id,
            outcome=r.outcome.value,
            alumni_id=r.alumni_id,
            career_record_id=r.career_record_id,
            detail=r.detail,
            dedup_candidate_ids=r.dedup_candidate_ids,
        )
        for r in results
    ]

    counts = dict.fromkeys(CommitOutcome, 0)
    for r in results:
        counts[r.outcome] += 1

    logger.info(
        "batch committed: batch_id=%d snapshot_id=%d created=%d linked=%d pending_dedup=%d",
        body.batch_id,
        body.snapshot_id,
        counts[CommitOutcome.created],
        counts[CommitOutcome.linked],
        counts[CommitOutcome.pending_dedup],
    )

    return CommitBatchResultOut(
        batch_id=body.batch_id,
        snapshot_id=body.snapshot_id,
        total=len(results),
        created=counts[CommitOutcome.created],
        linked=counts[CommitOutcome.linked],
        pending_dedup=counts[CommitOutcome.pending_dedup],
        skipped_error=counts[CommitOutcome.skipped_error],
        skipped_no_employer=counts[CommitOutcome.skipped_no_employer],
        rows=row_outs,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/alumni/{alumni_id}/validate
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/alumni/{alumni_id}/validate",
    summary="Curator validates or rejects an alumni record (D-024 gate)",
)
def validate_alumni(
    alumni_id: int,
    body: ValidateAlumniIn,
    user: AuthenticatedUser = Depends(require_permission("alumni:validate")),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Curator gate: set validation_status to 'validated' or 'rejected' (D-024).

    Only ``validated`` alumni appear in analytics (D-047).
    The pipeline never sets ``validated`` — this endpoint is the only path.

    ``action`` must be one of ``"validate"`` or ``"reject"``.
    ``reason`` is optional free text recorded in the audit log.

    Permission required: ``alumni:validate`` (Admin, Data Curator).
    """
    if body.action not in _VALID_VALIDATE_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action must be one of {sorted(_VALID_VALIDATE_ACTIONS)}",
        )

    alumni = session.get(Alumni, alumni_id)
    if alumni is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alumni {alumni_id} not found.",
        )

    old_status = str(alumni.validation_status)
    new_status = (
        ValidationStatus.validated if body.action == "validate" else ValidationStatus.rejected
    )

    alumni.validation_status = new_status

    write_audit_entry(
        session,
        table_name="alumni",
        record_id=str(alumni_id),
        action_type="UPDATE",
        old_values={"validation_status": old_status},
        new_values={
            "validation_status": str(new_status),
            "reason": body.reason,
        },
        changed_by=user.user_id,
    )

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Unexpected error setting validation_status on alumni %d", alumni_id)
        raise

    logger.info(
        "alumni %s: alumni_id=%d actor=%d reason=%r",
        body.action,
        alumni_id,
        user.user_id,
        body.reason,
    )

    return {
        "alumni_id": alumni_id,
        "validation_status": str(new_status),
        "changed_by": user.user_id,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/alumni/{alumni_id}
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/alumni/{alumni_id}",
    summary="Get an alumni record by ID",
)
def get_alumni(
    alumni_id: int,
    _user: AuthenticatedUser = Depends(require_permission("alumni:read")),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Return a single Alumni record by PK.

    Permission required: ``alumni:read``.
    """
    alumni = session.get(Alumni, alumni_id)
    if alumni is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alumni {alumni_id} not found.",
        )
    return {
        "alumni_id": alumni.alumni_id,
        "public_id": alumni.public_id,
        "full_name": alumni.full_name,
        "university": alumni.university,
        "study_program_id": alumni.study_program_id,
        "graduation_year": alumni.graduation_year,
        "linkedin_url": alumni.linkedin_url,
        "validation_status": str(alumni.validation_status),
        "source_id": alumni.source_id,
        "created_at": alumni.created_at.isoformat() if alumni.created_at else None,
        "updated_at": alumni.updated_at.isoformat() if alumni.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/alumni  (list pending)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/alumni",
    summary="List alumni records filtered by validation_status",
)
def list_alumni(
    validation_status: str | None = None,
    _user: AuthenticatedUser = Depends(require_permission("alumni:read")),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Return alumni records, optionally filtered by validation_status.

    Supported values: ``pending``, ``validated``, ``rejected``.
    Permission required: ``alumni:read``.
    """
    q = select(Alumni)
    if validation_status:
        try:
            vs = ValidationStatus(validation_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown validation_status {validation_status!r}",
            ) from None
        q = q.where(Alumni.validation_status == vs)

    rows = list(session.scalars(q.order_by(Alumni.alumni_id)).all())
    return {
        "total": len(rows),
        "items": [
            {
                "alumni_id": a.alumni_id,
                "full_name": a.full_name,
                "study_program_id": a.study_program_id,
                "graduation_year": a.graduation_year,
                "validation_status": str(a.validation_status),
            }
            for a in rows
        ],
    }
