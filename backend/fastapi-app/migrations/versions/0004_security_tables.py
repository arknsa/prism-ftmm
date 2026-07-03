"""RBAC security tables: role, permission, role_permission, app_user.

APP_USER is keyed by the Supabase user UUID (D-043). No auth enforcement yet;
that is Phase 2. AUDIT_LOG (P1.7) will FK into app_user and is added in S2.

Revision ID: 0004_security_tables
Revises: 0003_refresh_snapshot
Create Date: 2026-06-30

Decisions: D-026, D-032, D-036, D-043.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_security_tables"
down_revision: str | None = "0003_refresh_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role",
        sa.Column("role_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("role_id", name="pk_role"),
        sa.UniqueConstraint("role_name", name="uq_role_name"),
    )

    op.create_table(
        "permission",
        sa.Column("permission_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("permission_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("permission_id", name="pk_permission"),
        sa.UniqueConstraint("permission_name", name="uq_permission_name"),
    )

    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_role_permission"),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.role_id"],
            name="fk_role_permission_role",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permission.permission_id"],
            name="fk_role_permission_permission",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    op.create_table(
        "app_user",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supabase_uuid", UUID(as_uuid=False), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_app_user"),
        sa.UniqueConstraint("supabase_uuid", name="uq_app_user_supabase_uuid"),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.role_id"],
            name="fk_app_user_role",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("app_user")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
