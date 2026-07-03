"""Career record model.

One alumnus can have many CAREER_RECORDs; exactly one may have is_current=True
per alumnus, enforced by a partial unique index (D-020/D-029).

source_id is NOT NULL per D-041: every career record must declare its provenance.

seniority and snapshot_id are nullable in Phase 1:
  - seniority is assigned by the normalization pipeline in Phase 3 (P3.9).
  - snapshot_id is assigned when the record is committed under a quarter in Phase 4 (P4.5).

Decisions: D-020, D-021, D-028, D-029, D-041.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CareerRecord(Base):
    """Per-alumnus career entry, tagged with snapshot and source provenance (D-041).

    is_current marks the alumnus's present role. The partial unique index
    `uq_career_one_current_per_alumni` (defined in migration 0008) enforces that
    exactly one career record per alumnus can have is_current=True (D-020).
    """

    __tablename__ = "career_record"

    career_record_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    alumni_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("alumni.alumni_id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("company.company_id", ondelete="RESTRICT"),
        nullable=False,
    )
    role_title: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    seniority: Mapped[str | None] = mapped_column(
        sa.String(100), nullable=True
    )  # assigned in Phase 3 (P3.9)
    is_current: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.false())
    snapshot_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("refresh_snapshot.snapshot_id", ondelete="SET NULL"),
        nullable=True,
    )  # assigned at snapshot commit in Phase 4 (P4.5)
    source_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("capture_source.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    captured_on: Mapped[datetime.date | None] = mapped_column(sa.Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
