"""Staging models for the Phase 3 import pipeline (P3.1).

ImportBatch: one row per file upload / CLI import run.
StagingRow:  one row per body row in the source file; carries raw cells and
             the common candidate shape (Artifact A1 / IMPORT_FILE_FORMAT_SPEC.md).

Decisions: D-033, D-046 (source provenance), D-031 (FastAPI gateway).
"""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ImportBatch(Base):
    """Metadata record for a single import run (P3.1).

    created_by is nullable to support CLI/system imports where there is no
    request-scoped actor, consistent with audit_log.changed_by nullability.

    status values:
      "pending"  — initial; row staging in progress
      "complete" — all rows successfully staged
      "failed"   — parse aborted due to a structural file error
    """

    __tablename__ = "import_batch"

    batch_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("capture_source.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    parsed_rows: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    error_rows: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default=sa.text("'pending'")
    )
    created_by: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("app_user.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class StagingRow(Base):
    """One staged row from a source file (P3.1).

    Carries both the raw cell values (raw_*) and the common candidate shape
    defined by Artifact A1 (IMPORT_FILE_FORMAT_SPEC.md). Later normalizers
    (S3–S5) read from these fields without re-parsing.

    row_status values: "pending" (parseable) | "error" (missing required field).
    row_error holds the error message when row_status is "error".

    raw_extra captures every column not in the A1 spec as {column: value} JSONB.
    """

    __tablename__ = "staging_row"

    staging_row_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("import_batch.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # common candidate shape (Artifact A1)
    raw_full_name: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    raw_study_program: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    raw_graduation_year: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    raw_employer: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    raw_role_title: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    raw_location: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    raw_linkedin_url: Mapped[str | None] = mapped_column(sa.String(1000), nullable=True)
    raw_extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # per-row parse status
    row_status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, server_default=sa.text("'pending'")
    )
    row_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
