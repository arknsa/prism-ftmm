"""Snapshot model.

REFRESH_SNAPSHOT stores per-quarter metadata. CAREER_RECORD will FK into this
table in Phase 1 Session S2 (P1.4). No FK dependencies from this table.

Decisions: D-006, D-007, D-021.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RefreshSnapshot(Base):
    """Quarterly refresh metadata record (D-021).

    quarter_label uniquely identifies a snapshot quarter, e.g. "2025-Q1".
    All CAREER_RECORDs committed during a quarterly refresh are tagged with
    this snapshot's snapshot_id to support point-in-time reporting.
    """

    __tablename__ = "refresh_snapshot"

    snapshot_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    quarter_label: Mapped[str] = mapped_column(sa.String(20), nullable=False, unique=True)
    refresh_date: Mapped[datetime.date] = mapped_column(sa.Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
