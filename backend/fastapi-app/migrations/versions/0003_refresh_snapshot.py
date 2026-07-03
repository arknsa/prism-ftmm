"""Refresh snapshot table: refresh_snapshot.

Stores per-quarter metadata. CAREER_RECORD will FK into this table in Phase 1 S2 (P1.4).
No FK dependencies from this table itself.

Revision ID: 0003_refresh_snapshot
Revises: 0002_reference_tables
Create Date: 2026-06-30

Decisions: D-006, D-007, D-021.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_snapshot",
        sa.Column("snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quarter_label", sa.String(20), nullable=False),
        sa.Column("refresh_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_refresh_snapshot"),
        sa.UniqueConstraint("quarter_label", name="uq_refresh_snapshot_quarter_label"),
    )


def downgrade() -> None:
    op.drop_table("refresh_snapshot")
