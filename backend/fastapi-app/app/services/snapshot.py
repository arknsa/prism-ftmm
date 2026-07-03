"""Snapshot creation service (P4.4).

Manages REFRESH_SNAPSHOT lifecycle — one snapshot per quarter (D-021).

  open_snapshot(quarter_label, refresh_date, notes, session) → RefreshSnapshot
  get_snapshot(snapshot_id, session)                         → RefreshSnapshot | None
  get_snapshot_by_label(quarter_label, session)              → RefreshSnapshot | None
  list_snapshots(session)                                    → list[RefreshSnapshot]

Design constraints (D-006, D-007, D-021, D-031):
- One REFRESH_SNAPSHOT per quarter_label (enforced by DB unique constraint).
- Opening a snapshot that already exists raises ValueError (idempotency guard).
- These functions do NOT commit; the caller owns the transaction (D-031).
- Snapshot metadata only: no alumni/career data committed here (that is P4.5).

Decisions: D-006, D-007, D-021, D-031.
"""

from __future__ import annotations

import datetime
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.snapshot import RefreshSnapshot

# Quarter label format: YYYY-Q[1-4]
_QUARTER_LABEL_RE = re.compile(r"^\d{4}-Q[1-4]$")


def _validate_quarter_label(quarter_label: str) -> None:
    """Raise ValueError if quarter_label does not match YYYY-Q[1-4] format."""
    if not _QUARTER_LABEL_RE.match(quarter_label):
        raise ValueError(
            f"Invalid quarter_label {quarter_label!r}. "
            "Expected format: YYYY-Q[1-4] (e.g. '2025-Q1')."
        )


def open_snapshot(
    quarter_label: str,
    refresh_date: datetime.date | None = None,
    notes: str | None = None,
    session: Session = None,  # type: ignore[assignment]
) -> RefreshSnapshot:
    """Create and register a new REFRESH_SNAPSHOT for a quarter.

    Args:
        quarter_label: e.g. "2025-Q1". Must match YYYY-Q[1-4].
        refresh_date: optional date the refresh was run; defaults to today.
        notes: optional curator notes for this snapshot.
        session: active SQLAlchemy session — caller owns commit.

    Returns:
        The new RefreshSnapshot instance (added to session, not committed).

    Raises:
        ValueError: if quarter_label format is invalid or snapshot already exists.
    """
    _validate_quarter_label(quarter_label)

    existing = get_snapshot_by_label(quarter_label, session)
    if existing is not None:
        raise ValueError(
            f"Snapshot for quarter {quarter_label!r} already exists "
            f"(snapshot_id={existing.snapshot_id})."
        )

    snapshot = RefreshSnapshot(
        quarter_label=quarter_label,
        refresh_date=refresh_date or datetime.date.today(),
        notes=notes,
    )
    session.add(snapshot)
    return snapshot


def get_snapshot(snapshot_id: int, session: Session) -> RefreshSnapshot | None:
    """Return a RefreshSnapshot by PK, or None if not found."""
    return session.get(RefreshSnapshot, snapshot_id)


def get_snapshot_by_label(quarter_label: str, session: Session) -> RefreshSnapshot | None:
    """Return a RefreshSnapshot by quarter_label, or None if not found."""
    return session.scalar(
        select(RefreshSnapshot).where(RefreshSnapshot.quarter_label == quarter_label)
    )


def list_snapshots(session: Session) -> list[RefreshSnapshot]:
    """Return all snapshots ordered by quarter_label ascending."""
    return list(
        session.scalars(select(RefreshSnapshot).order_by(RefreshSnapshot.quarter_label)).all()
    )
