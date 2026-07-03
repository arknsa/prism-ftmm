"""Company normalization tables: company, company_alias.

COMPANY holds one canonical record per employer. COMPANY_ALIAS maps every raw
employer string to its canonical company. industry_id and location_id on COMPANY
are nullable — classification is assigned by curators in Phase 4.

No redundant `country` column on COMPANY (Q-021 resolution).
All FK targets declared explicitly (Q-023 resolution).

Revision ID: 0005_company
Revises: 0004_security_tables
Create Date: 2026-06-30

Decisions: D-008, D-017, D-018, D-019; Q-021, Q-023.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_company"
down_revision: str | None = "0004_security_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("company_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_name", sa.String(300), nullable=False),
        sa.Column("industry_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("company_id", name="pk_company"),
        sa.UniqueConstraint("canonical_name", name="uq_company_canonical_name"),
        sa.ForeignKeyConstraint(
            ["industry_id"],
            ["industry.industry_id"],
            name="fk_company_industry",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["location.location_id"],
            name="fk_company_location",
            ondelete="SET NULL",
        ),
    )

    op.create_table(
        "company_alias",
        sa.Column("alias_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("alias_name", sa.String(300), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("alias_id", name="pk_company_alias"),
        sa.UniqueConstraint("alias_name", name="uq_company_alias_name"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.company_id"],
            name="fk_company_alias_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["capture_source.source_id"],
            name="fk_company_alias_source",
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("company_alias")
    op.drop_table("company")
