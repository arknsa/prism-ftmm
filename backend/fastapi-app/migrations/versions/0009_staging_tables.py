"""Staging tables for the Phase 3 import pipeline (P3.1).

Two new tables — import_batch and staging_row — form the landing zone for raw
imported data before normalization and validation. Both tables are additive: no
existing table is altered.

import_batch:   one row per file upload / CLI import run; tracks source,
                filename, row counts, status, and the actor who triggered the
                import (nullable for CLI/system imports, consistent with
                audit_log.changed_by nullability).

staging_row:    one row per body row in the source file; carries both the raw
                parsed cells AND the common candidate shape consumed by the
                S3–S5 normalizers/matchers (see IMPORT_FILE_FORMAT_SPEC.md /
                Artifact A1). raw_extra holds every extra column not in the
                A1 spec as {col: value} JSONB.

row_status values: "pending" (parseable, awaiting pipeline) | "error" (parse
failure — missing required field). Status is never "validated"/"rejected" in
staging; those states live on the alumni table after Phase 4 commit.

Decisions: D-033 (manual import workflow), D-046 (source provenance),
           D-031 (FastAPI gateway), D-025 (audit; wired in S2).

Revision ID: 0009_staging_tables
Revises: 0008_career_record_indexes_constraints
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0009_staging_tables"
down_revision: str | None = "0008_career_record_indexes_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # import_batch — one row per import run                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "import_batch",
        sa.Column("batch_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("parsed_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        # "pending" → awaiting pipeline; "complete" → all rows staged; "failed" → parse aborted
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        # NULL for CLI / system imports (no request context)
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("batch_id", name="pk_import_batch"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["capture_source.source_id"],
            name="fk_import_batch_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.user_id"],
            name="fk_import_batch_created_by",
            ondelete="SET NULL",
        ),
    )

    op.create_index("idx_import_batch_source", "import_batch", ["source_id"])
    op.create_index("idx_import_batch_created_by", "import_batch", ["created_by"])
    op.create_index("idx_import_batch_status", "import_batch", ["status"])

    # ------------------------------------------------------------------ #
    # staging_row — one row per body row in the source file               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "staging_row",
        sa.Column("staging_row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        # 1-indexed position in the file (header = row 1, first body row = row 2)
        sa.Column("row_number", sa.Integer(), nullable=False),
        # ---- common candidate shape (Artifact A1) -------------------- #
        sa.Column("raw_full_name", sa.String(500), nullable=True),
        sa.Column("raw_study_program", sa.String(500), nullable=True),
        sa.Column("raw_graduation_year", sa.Integer(), nullable=True),
        # career-candidate fields; NULL when employer absent in source
        sa.Column("raw_employer", sa.String(500), nullable=True),
        sa.Column("raw_role_title", sa.String(500), nullable=True),
        sa.Column("raw_location", sa.String(500), nullable=True),
        sa.Column("raw_linkedin_url", sa.String(1000), nullable=True),
        # all extra / source-specific columns as {col: value}
        sa.Column("raw_extra", JSONB(), nullable=True),
        # ---- per-row parse status ------------------------------------ #
        # "pending" | "error"
        sa.Column(
            "row_status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("row_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("staging_row_id", name="pk_staging_row"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batch.batch_id"],
            name="fk_staging_row_batch",
            ondelete="CASCADE",
        ),
    )

    op.create_index("idx_staging_row_batch", "staging_row", ["batch_id"])
    op.create_index("idx_staging_row_status", "staging_row", ["row_status"])


def downgrade() -> None:
    op.drop_index("idx_staging_row_status", table_name="staging_row")
    op.drop_index("idx_staging_row_batch", table_name="staging_row")
    op.drop_table("staging_row")

    op.drop_index("idx_import_batch_status", table_name="import_batch")
    op.drop_index("idx_import_batch_created_by", table_name="import_batch")
    op.drop_index("idx_import_batch_source", table_name="import_batch")
    op.drop_table("import_batch")
