"""Reference / taxonomy tables: study_program, industry, location, capture_source.

These are the parent look-up tables that all other entities FK-reference.
No FK dependencies within this migration.

Revision ID: 0002_reference_tables
Revises: 0001_baseline
Create Date: 2026-06-30

Decisions: D-003, D-004 (is_ftmm_valid), D-009, D-010, D-018, D-019,
           D-042 (industry_name + sector_name), D-049 (trust_tier).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_program",
        sa.Column("program_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("program_name", sa.String(200), nullable=False),
        sa.Column("degree_level", sa.String(50), nullable=False),
        sa.Column("is_ftmm_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("program_id", name="pk_study_program"),
        sa.UniqueConstraint("program_name", name="uq_study_program_name"),
    )

    op.create_table(
        "industry",
        sa.Column("industry_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("industry_name", sa.String(200), nullable=False),
        sa.Column("sector_name", sa.String(200), nullable=False),
        sa.Column("taxonomy_code", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("industry_id", name="pk_industry"),
        sa.UniqueConstraint("industry_name", name="uq_industry_name"),
    )

    op.create_table(
        "location",
        sa.Column("location_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("location_id", name="pk_location"),
    )

    op.create_table(
        "capture_source",
        sa.Column("source_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("trust_tier", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("source_id", name="pk_capture_source"),
        sa.UniqueConstraint("source_type", name="uq_capture_source_type"),
    )


def downgrade() -> None:
    op.drop_table("capture_source")
    op.drop_table("location")
    op.drop_table("industry")
    op.drop_table("study_program")
