"""Dedup candidate queue model (P4.3).

A DedupCandidate row is created when a staged row matches one or more existing
Alumni via Tier-2 (name+program+year) and needs curator review before the
staged row can be committed under a snapshot.

Curator actions:
  "merge"         — staged row belongs to the same real person as the linked alumni.
                    The import pipeline will use the existing alumni_id.
  "keep_separate" — staged row represents a distinct person despite the key match.
                    A new Alumni will be created at commit time.
  "pending"       — awaiting curator decision (default).

Decisions: D-044, D-045, D-024, D-031.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DedupCandidate(Base):
    """Curator review queue entry for a Tier-2 dedup match (D-045).

    Links a staging_row to the candidate Alumni it matched by Tier-2 key.
    If multiple Alumni match the same staging row, one DedupCandidate row
    is created per matched Alumni.

    resolution values:
      "pending"       — awaiting curator decision
      "merge"         — curator confirmed: same person as matched_alumni_id
      "keep_separate" — curator confirmed: different person
    """

    __tablename__ = "dedup_candidate"

    dedup_candidate_id: Mapped[int] = mapped_column(
        sa.Integer, primary_key=True, autoincrement=True
    )
    staging_row_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("staging_row.staging_row_id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_alumni_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("alumni.alumni_id", ondelete="CASCADE"),
        nullable=False,
    )
    resolution: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'pending'"),
    )
    resolved_by: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("app_user.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
