"""Company and alias normalization models.

COMPANY holds one canonical record per employer. COMPANY_ALIAS maps every raw
employer string encountered during import onto its canonical company, enabling
consistent industry and location attribution across sources.

Redundant `country` column intentionally absent from COMPANY (Q-021 resolution).
All FK targets declared explicitly (Q-023 resolution).

Decisions: D-008, D-017, D-018, D-019; Q-021, Q-023.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Company(Base):
    """Canonical employer record (D-017).

    industry_id and location_id are nullable at creation time: a company discovered
    during import may not have classification yet. Curators assign both via the
    company-alias management screen in Phase 4 (P4.10).
    """

    __tablename__ = "company"

    company_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(sa.String(300), nullable=False, unique=True)
    industry_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("industry.industry_id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("location.location_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class CompanyAlias(Base):
    """Raw employer string → canonical company mapping (D-017).

    Each alias_name is unique: a raw string is unambiguously linked to exactly
    one canonical company. source_id records which data source introduced the alias.
    """

    __tablename__ = "company_alias"

    alias_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("company.company_id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_name: Mapped[str] = mapped_column(sa.String(300), nullable=False, unique=True)
    source_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("capture_source.source_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
