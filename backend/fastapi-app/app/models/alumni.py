"""Alumni model with all blocker-resolution deltas applied.

Deltas from the blocker-resolution pass (D-040–D-047):
  D-040: university text column (default "Universitas Airlangga"), enforced by
         the curator validation workflow — not a relational entity.
  D-044: public_id UUID as system identity; linkedin_url nullable + partial-unique.
  D-046: source_id FK (primary provenance); NOT NULL.
  D-047: validation_status enum {pending, validated, rejected}; only "validated"
         rows enter analytics.

Decisions: D-003, D-004, D-023, D-024, D-040, D-044, D-046, D-047.
"""

from __future__ import annotations

import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ValidationStatus(StrEnum):
    """Curator-controlled validation states for an alumni record (D-047).

    Only `validated` rows are included in analytics. `rejected` rows are retained
    for audit trail and to prevent re-import of known-bad records (anti-churn).
    """

    pending = "pending"
    validated = "validated"
    rejected = "rejected"


# PostgreSQL enum type — created/dropped by the Alembic migration (0006_alumni).
_validation_status_pg = sa.Enum(
    ValidationStatus,
    name="validationstatus",
    create_type=False,  # lifecycle managed by the migration, not the model
)


class Alumni(Base):
    """Core alumni record (D-023, D-040, D-044, D-046, D-047).

    Identity: public_id (UUID, system-generated, unique) is the stable identity
    key. linkedin_url is a secondary dedup signal — nullable and partial-unique
    (present rows must be unique; NULL rows are not constrained).

    University: stored as an attribute (default "Universitas Airlangga") and
    validated by the curator workflow, not as a relational entity (D-040).

    Provenance: source_id (NOT NULL) records which data source introduced this
    record (D-046). Full mutation history is in AUDIT_LOG (Phase 4, P4.6).
    """

    __tablename__ = "alumni"

    alumni_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        unique=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    full_name: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    university: Mapped[str] = mapped_column(
        sa.String(200), nullable=False, server_default=sa.text("'Universitas Airlangga'")
    )
    study_program_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("study_program.program_id", ondelete="RESTRICT"),
        nullable=False,
    )
    graduation_year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        _validation_status_pg,
        nullable=False,
        server_default=sa.text("'pending'"),
    )
    source_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("capture_source.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
