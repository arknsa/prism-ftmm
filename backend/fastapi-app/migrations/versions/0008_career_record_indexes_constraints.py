"""Career record table plus all filter/search indexes and constraints.

P1.4 (CAREER_RECORD) + P1.8 (filter indexes) + P1.9 (constraints) are bundled
here because the indexes and constraints are addenda to the same schema layer
and separating them would create pointless intermediate migrations.

Partial unique index `uq_career_one_current_per_alumni` enforces exactly one
is_current=true per alumnus (D-020/D-029). It is a WHERE-clause partial index
and cannot be expressed as a table-level UNIQUE constraint.

seniority and snapshot_id are nullable: filled in Phase 3 (P3.9) and Phase 4
(P4.5) respectively. source_id is NOT NULL per D-041.

Revision ID: 0008_career_record_indexes_constraints
Revises: 0007_audit_log
Create Date: 2026-06-30

Decisions: D-020, D-021, D-028, D-029, D-041.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # P1.4 — CAREER_RECORD table                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "career_record",
        sa.Column("career_record_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alumni_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role_title", sa.String(300), nullable=False),
        sa.Column("seniority", sa.String(100), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("snapshot_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("captured_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("career_record_id", name="pk_career_record"),
        sa.ForeignKeyConstraint(
            ["alumni_id"],
            ["alumni.alumni_id"],
            name="fk_career_record_alumni",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.company_id"],
            name="fk_career_record_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["refresh_snapshot.snapshot_id"],
            name="fk_career_record_snapshot",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["capture_source.source_id"],
            name="fk_career_record_source",
            ondelete="RESTRICT",
        ),
    )

    # ------------------------------------------------------------------ #
    # P1.9 — Partial unique constraint: one current career record          #
    #        per alumnus (D-020/D-029).                                   #
    # ------------------------------------------------------------------ #
    op.create_index(
        "uq_career_one_current_per_alumni",
        "career_record",
        ["alumni_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # ------------------------------------------------------------------ #
    # P1.8 — Filter indexes (D-028)                                        #
    # ------------------------------------------------------------------ #

    # alumni table
    op.create_index("idx_alumni_graduation_year", "alumni", ["graduation_year"])
    op.create_index("idx_alumni_study_program", "alumni", ["study_program_id"])
    op.create_index("idx_alumni_validation_status", "alumni", ["validation_status"])

    # career_record table
    op.create_index("idx_career_company", "career_record", ["company_id"])
    op.create_index("idx_career_snapshot", "career_record", ["snapshot_id"])
    op.create_index("idx_career_is_current", "career_record", ["is_current"])
    op.create_index("idx_career_alumni", "career_record", ["alumni_id"])

    # company table
    op.create_index("idx_company_industry", "company", ["industry_id"])
    op.create_index("idx_company_location", "company", ["location_id"])

    # ------------------------------------------------------------------ #
    # P1.8 — Search indexes (D-028)                                        #
    # ------------------------------------------------------------------ #

    # linkedin_url: the partial unique index `uq_alumni_linkedin_url` created in
    # migration 0006 already serves as the lookup index — PostgreSQL uses unique
    # indexes for equality lookups. A separate non-unique index is redundant and
    # would add write overhead on every alumni INSERT/UPDATE.
    # canonical_name is covered by its UNIQUE constraint on company.
    pass


def downgrade() -> None:
    # company filter indexes
    op.drop_index("idx_company_location", table_name="company")
    op.drop_index("idx_company_industry", table_name="company")

    # career_record filter indexes
    op.drop_index("idx_career_alumni", table_name="career_record")
    op.drop_index("idx_career_is_current", table_name="career_record")
    op.drop_index("idx_career_snapshot", table_name="career_record")
    op.drop_index("idx_career_company", table_name="career_record")

    # alumni filter indexes
    op.drop_index("idx_alumni_validation_status", table_name="alumni")
    op.drop_index("idx_alumni_study_program", table_name="alumni")
    op.drop_index("idx_alumni_graduation_year", table_name="alumni")

    # partial unique constraint
    op.drop_index("uq_career_one_current_per_alumni", table_name="career_record")

    # table
    op.drop_table("career_record")
