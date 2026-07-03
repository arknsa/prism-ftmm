"""Audit log table: audit_log.

Stores an immutable record of every data mutation routed through FastAPI (D-025).
changed_by FK to app_user is nullable to support system/script mutations before
the auth layer (Phase 2) is wired.

old_values and new_values use native PostgreSQL JSONB for efficient storage and
future query-ability (e.g. filtering mutations by field value in Phase 7).

Revision ID: 0007_audit_log
Revises: 0006_alumni
Create Date: 2026-06-30

Decisions: D-025, D-036; Q-023 (FK to app_user declared explicitly).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_audit_log"
down_revision: str | None = "0006_alumni"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.String(100), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("old_values", JSONB(), nullable=True),
        sa.Column("new_values", JSONB(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("audit_id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            ["app_user.user_id"],
            name="fk_audit_log_changed_by",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
