"""Snapshot management endpoints (P4.4, P4.11 backend).

  POST /api/v1/snapshots          — open a new quarter snapshot
  GET  /api/v1/snapshots          — list all snapshots
  GET  /api/v1/snapshots/{id}     — get a single snapshot

Permission required: snapshot:manage (Admin, Data Curator).

Decisions: D-006, D-007, D-021, D-025, D-031.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.schemas.auth import AuthenticatedUser
from app.schemas.snapshot import SnapshotCreateIn, SnapshotListOut, SnapshotOut
from app.services.audit import write_audit_entry
from app.services.snapshot import (
    get_snapshot,
    list_snapshots,
    open_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])


# ---------------------------------------------------------------------------
# POST /api/v1/snapshots
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a new quarterly refresh snapshot",
)
def create_snapshot(
    body: SnapshotCreateIn,
    user: AuthenticatedUser = Depends(require_permission("snapshot:manage")),
    session: Session = Depends(get_session),
) -> SnapshotOut:
    """Create a new REFRESH_SNAPSHOT for the given quarter.

    Fails with 400 if a snapshot for that quarter already exists.
    Permission required: ``snapshot:manage`` (Admin, Data Curator).
    """
    try:
        snapshot = open_snapshot(
            quarter_label=body.quarter_label,
            refresh_date=body.refresh_date,
            notes=body.notes,
            session=session,
        )
        session.flush()  # populate snapshot_id for audit

        write_audit_entry(
            session,
            table_name="refresh_snapshot",
            record_id=str(snapshot.snapshot_id),
            action_type="INSERT",
            new_values={
                "quarter_label": snapshot.quarter_label,
                "refresh_date": str(snapshot.refresh_date),
                "notes": snapshot.notes,
            },
            changed_by=user.user_id,
        )

        session.commit()

    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        logger.exception("Unexpected error creating snapshot")
        raise

    logger.info(
        "snapshot created: id=%d quarter=%r actor=%d",
        snapshot.snapshot_id,
        snapshot.quarter_label,
        user.user_id,
    )
    return SnapshotOut.model_validate(snapshot)


# ---------------------------------------------------------------------------
# GET /api/v1/snapshots
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SnapshotListOut,
    summary="List all quarterly snapshots",
)
def get_all_snapshots(
    _user: AuthenticatedUser = Depends(require_permission("snapshot:manage")),
    session: Session = Depends(get_session),
) -> SnapshotListOut:
    """Return all REFRESH_SNAPSHOT rows ordered by quarter_label.

    Permission required: ``snapshot:manage``.
    """
    snapshots = list_snapshots(session)
    return SnapshotListOut(
        total=len(snapshots),
        items=[SnapshotOut.model_validate(s) for s in snapshots],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/snapshots/{snapshot_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{snapshot_id}",
    response_model=SnapshotOut,
    summary="Get a single snapshot by ID",
)
def get_snapshot_by_id(
    snapshot_id: int,
    _user: AuthenticatedUser = Depends(require_permission("snapshot:manage")),
    session: Session = Depends(get_session),
) -> SnapshotOut:
    """Return a single REFRESH_SNAPSHOT by PK.

    Permission required: ``snapshot:manage``.
    """
    snap = get_snapshot(snapshot_id, session)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found.",
        )
    return SnapshotOut.model_validate(snap)
