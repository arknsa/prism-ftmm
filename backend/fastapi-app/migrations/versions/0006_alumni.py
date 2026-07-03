"""Alumni table with all blocker-resolution deltas.

Creates the `validationstatus` PostgreSQL enum before the table, and drops it
after the table on downgrade. The partial unique index on linkedin_url enforces
uniqueness only for non-NULL values (D-044).

DB-side default for public_id uses gen_random_uuid() — available on Supabase
(PostgreSQL 14+, pgcrypto not required; built into core PG).

Revision ID: 0006_alumni
Revises: 0005_company
Create Date: 2026-06-30

Decisions: D-003, D-004, D-023, D-024, D-040, D-044, D-046, D-047.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006_alumni"
down_revision: str | None = "0005_company"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_validation_status_enum = sa.Enum(
    "pending", "validated", "rejected", name="validationstatus"
)


def upgrade() -> None:
    op.create_table(
        "alumni",
        sa.Column("alumni_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "public_id",
            UUID(as_uuid=False),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("full_name", sa.String(300), nullable=False),
        sa.Column(
            "university",
            sa.String(200),
            nullable=False,
            server_default=sa.text("'Universitas Airlangga'"),
        ),
        sa.Column("study_program_id", sa.Integer(), nullable=False),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column(
            "validation_status",
            # create_type=True: Alembic creates the PG enum as part of this table DDL.
            sa.Enum(
                "pending",
                "validated",
                "rejected",
                name="validationstatus",
                create_type=True,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("source_id", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("alumni_id", name="pk_alumni"),
        sa.UniqueConstraint("public_id", name="uq_alumni_public_id"),
        sa.ForeignKeyConstraint(
            ["study_program_id"],
            ["study_program.program_id"],
            name="fk_alumni_study_program",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["capture_source.source_id"],
            name="fk_alumni_source",
            ondelete="RESTRICT",
        ),
    )

    # Partial unique index: linkedin_url must be unique when present (D-044).
    op.create_index(
        "uq_alumni_linkedin_url",
        "alumni",
        ["linkedin_url"],
        unique=True,
        postgresql_where=sa.text("linkedin_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_alumni_linkedin_url", table_name="alumni")
    op.drop_table("alumni")
    # Drop the PG enum type after the table that uses it is gone.
    _validation_status_enum.drop(op.get_bind(), checkfirst=True)
