"""Dedup candidate review queue table for the Phase 4 commit pipeline (P4.3).

One dedup_candidate row is created when a staged row matches one or more existing
Alumni via the Tier-2 key (name + program + year) and needs curator review before
the staged row can be committed under a snapshot (D-045: no auto-merge).

This table is required by app.services.dedup_queue and app.services.commit, whose
models were registered on Base.metadata (app.models.__init__) ahead of this
migration. Without it `alembic upgrade head` produces a schema the running app
depends on but that does not exist — the dedup/commit endpoints raise
UndefinedTable. (The test suite mocks the session, so it does not surface here.)

resolution values: "pending" (default, awaiting curator) | "merge" (same person
as matched_alumni_id) | "keep_separate" (distinct person). Mirrors
app/models/dedup.py exactly; index/FK naming follows the 0009 house style.

Decisions: D-024 (curator-only resolve), D-031 (FastAPI gateway),
           D-044 / D-045 (Tier-2 human decision).

Revision ID: 0010_dedup_candidate
Revises: 0009_staging_tables
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dedup_candidate",
        sa.Column("dedup_candidate_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("staging_row_id", sa.Integer(), nullable=False),
        sa.Column("matched_alumni_id", sa.Integer(), nullable=False),
        # "pending" (default) | "merge" | "keep_separate"
        sa.Column(
            "resolution",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        # NULL until a curator resolves the candidate (FK app_user, SET NULL on delete)
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("dedup_candidate_id", name="pk_dedup_candidate"),
        sa.ForeignKeyConstraint(
            ["staging_row_id"],
            ["staging_row.staging_row_id"],
            name="fk_dedup_candidate_staging_row",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_alumni_id"],
            ["alumni.alumni_id"],
            name="fk_dedup_candidate_matched_alumni",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["app_user.user_id"],
            name="fk_dedup_candidate_resolved_by",
            ondelete="SET NULL",
        ),
    )

    op.create_index("idx_dedup_candidate_staging_row", "dedup_candidate", ["staging_row_id"])
    op.create_index("idx_dedup_candidate_matched_alumni", "dedup_candidate", ["matched_alumni_id"])
    op.create_index("idx_dedup_candidate_resolved_by", "dedup_candidate", ["resolved_by"])
    # get_pending_candidates filters on resolution = 'pending'
    op.create_index("idx_dedup_candidate_resolution", "dedup_candidate", ["resolution"])


def downgrade() -> None:
    op.drop_index("idx_dedup_candidate_resolution", table_name="dedup_candidate")
    op.drop_index("idx_dedup_candidate_resolved_by", table_name="dedup_candidate")
    op.drop_index("idx_dedup_candidate_matched_alumni", table_name="dedup_candidate")
    op.drop_index("idx_dedup_candidate_staging_row", table_name="dedup_candidate")
    op.drop_table("dedup_candidate")
