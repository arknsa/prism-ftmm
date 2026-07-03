"""Reference / taxonomy models.

These are the parent look-up tables that every other entity FK-references.
No FK dependencies on other Phase 1 tables — safe to create first.

Decisions: D-003, D-004 (is_ftmm_valid), D-009, D-010, D-018, D-019,
           D-042 (industry_name + sector_name), D-049 (static trust tier).
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StudyProgram(Base):
    """Approved FTMM study programs + any non-valid programs stored for rejection (D-003/D-004)."""

    __tablename__ = "study_program"

    program_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    program_name: Mapped[str] = mapped_column(sa.String(200), nullable=False, unique=True)
    degree_level: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    is_ftmm_valid: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.false()
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Industry(Base):
    """Industry taxonomy with granular name and parent sector grouping (D-042).

    industry_name: granular label (e.g. "Software Development").
    sector_name:   parent group  (e.g. "Technology").
    taxonomy_code: optional external reference code.
    """

    __tablename__ = "industry"

    industry_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    industry_name: Mapped[str] = mapped_column(sa.String(200), nullable=False, unique=True)
    sector_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    taxonomy_code: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Location(Base):
    """Geographic normalization table (D-019).

    country / province / city / region form a hierarchy; all fields except
    country are nullable to support partial-resolution entries.
    """

    __tablename__ = "location"

    location_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    province: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class CaptureSource(Base):
    """Data provenance / ingestion source with a static curator-assigned trust tier (D-049).

    trust_tier is a static integer; lower value = higher trust:
      1 = Verified Faculty Record (most trusted)
      2 = Tracer Study
      3 = LinkedIn
      4 = Alumni Form (deferred; row exists for completeness)

    Field was named confidence_level in Schema v1; renamed trust_tier per D-049
    to reflect that it is a curator-set static value, never computed.
    """

    __tablename__ = "capture_source"

    source_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    trust_tier: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
