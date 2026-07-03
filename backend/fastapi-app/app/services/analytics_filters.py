"""Shared filter contract and query-builder for analytics endpoints (P5.1).

All six aggregation endpoints (P5.3–P5.8) accept the same optional filter set:
  - study_program_id  : int   — filter to a single program
  - graduation_year   : int   — filter to a single cohort year
  - industry_id       : int   — filter to companies in this industry
  - company_id        : int   — filter to a specific employer
  - country           : str   — filter to alumni whose company is in this country
  - snapshot_id       : int   — restrict career records to a specific quarter (D-007)

All filters are applied to the validated-only alumni population (D-047):
  `ALUMNI.validation_status = 'validated'`

The query builder returns a list of SQLAlchemy WHERE clause elements that callers
append to their own queries.  Each clause is independent — callers can freely
JOIN additional tables before or after applying filters.

Decisions: D-007, D-047.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa

from app.models.alumni import Alumni, ValidationStatus
from app.models.career import CareerRecord
from app.models.company import Company
from app.models.reference import Location


@dataclass(frozen=True)
class AnalyticsFilters:
    """Validated filter set for analytics queries.

    All fields are optional.  ``None`` means "no filter on that dimension".
    """

    study_program_id: int | None = None
    graduation_year: int | None = None
    industry_id: int | None = None
    company_id: int | None = None
    country: str | None = None
    snapshot_id: int | None = None


def build_alumni_where(filters: AnalyticsFilters) -> list[sa.ColumnElement[bool]]:
    """Return WHERE clauses for queries rooted on the Alumni table.

    Always includes the validated-only guard (D-047).
    Joins to CareerRecord / Company are the caller's responsibility when
    industry_id, company_id, country, or snapshot_id filters are active.
    """
    clauses: list[sa.ColumnElement[bool]] = [
        Alumni.validation_status == ValidationStatus.validated,
    ]
    if filters.study_program_id is not None:
        clauses.append(Alumni.study_program_id == filters.study_program_id)
    if filters.graduation_year is not None:
        clauses.append(Alumni.graduation_year == filters.graduation_year)
    return clauses


def build_career_where(filters: AnalyticsFilters) -> list[sa.ColumnElement[bool]]:
    """Return WHERE clauses for queries rooted on CareerRecord (current roles only).

    Callers must JOIN Alumni (for validated guard + program/year filters) and
    Company (for industry/company filters).

    The ``country`` dimension is NOT included here because it requires a JOIN to
    the Location table that not every caller performs. Apply it separately via
    :func:`build_country_clause`, which restricts by a Company→Location subquery
    and therefore composes with any query that selects ``CareerRecord.company_id``.
    """
    clauses: list[sa.ColumnElement[bool]] = [
        CareerRecord.is_current.is_(True),
        Alumni.validation_status == ValidationStatus.validated,
    ]
    if filters.study_program_id is not None:
        clauses.append(Alumni.study_program_id == filters.study_program_id)
    if filters.graduation_year is not None:
        clauses.append(Alumni.graduation_year == filters.graduation_year)
    if filters.company_id is not None:
        clauses.append(CareerRecord.company_id == filters.company_id)
    if filters.industry_id is not None:
        clauses.append(Company.industry_id == filters.industry_id)
    if filters.snapshot_id is not None:
        clauses.append(CareerRecord.snapshot_id == filters.snapshot_id)
    return clauses


def build_country_clause(filters: AnalyticsFilters) -> sa.ColumnElement[bool] | None:
    """Return a WHERE clause restricting current career records to ``filters.country``.

    Returns ``None`` when no country filter is active. The clause is a
    ``CareerRecord.company_id IN (companies located in <country>)`` subquery so it
    can be appended to any query that references ``CareerRecord`` without needing
    an explicit Location JOIN. This keeps the country filter consistent across
    every analytics endpoint (D-007), not just geography and the directory.
    """
    if filters.country is None:
        return None
    companies_in_country = (
        sa.select(Company.company_id)
        .join(Location, Location.location_id == Company.location_id)
        .where(Location.country == filters.country)
    )
    return CareerRecord.company_id.in_(companies_in_country)
