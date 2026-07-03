"""Analytics aggregation service (P5.3–P5.8).

All queries operate on VALIDATED alumni only (D-047).  Employment semantics follow
D-048: alumni with a current CareerRecord are "Employed"; those without are "Not
Reported".  We never assert an unemployment rate.

Filter dimensions (D-007): study_program_id, graduation_year, industry_id,
company_id, country, snapshot_id — built via analytics_filters.py (P5.1).

All functions accept a SQLAlchemy Session and an AnalyticsFilters object; they
return plain dicts/lists that the API layer serialises.  No session.commit().

Decisions: D-007, D-021, D-042, D-047, D-048.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.alumni import Alumni, ValidationStatus
from app.models.career import CareerRecord
from app.models.company import Company
from app.models.reference import Industry, Location, StudyProgram
from app.models.snapshot import RefreshSnapshot
from app.services.analytics_filters import (
    AnalyticsFilters,
    build_alumni_where,
    build_career_where,
    build_country_clause,
)

# ---------------------------------------------------------------------------
# P5.2 — Filter-options
# ---------------------------------------------------------------------------


@dataclass
class FilterOptions:
    programs: list[dict[str, object]] = field(default_factory=list)
    graduation_years: list[int] = field(default_factory=list)
    industries: list[dict[str, object]] = field(default_factory=list)
    companies: list[dict[str, object]] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    snapshots: list[dict[str, object]] = field(default_factory=list)


def get_filter_options(session: Session) -> FilterOptions:
    """Return distinct values for each filter dimension (P5.2).

    Values are derived from the validated alumni / career population so the UI
    only shows options that will actually return results.
    """
    opts = FilterOptions()

    # Programs present in validated alumni
    rows = session.execute(
        sa.select(StudyProgram.program_id, StudyProgram.program_name)
        .join(Alumni, Alumni.study_program_id == StudyProgram.program_id)
        .where(Alumni.validation_status == ValidationStatus.validated)
        .distinct()
        .order_by(StudyProgram.program_name)
    ).all()
    opts.programs = [{"program_id": r.program_id, "program_name": r.program_name} for r in rows]

    # Graduation years present in validated alumni
    years = session.scalars(
        sa.select(Alumni.graduation_year)
        .where(Alumni.validation_status == ValidationStatus.validated)
        .distinct()
        .order_by(Alumni.graduation_year)
    ).all()
    opts.graduation_years = list(years)

    # Industries linked to companies with a current career record of a validated alumnus
    ind_rows = session.execute(
        sa.select(Industry.industry_id, Industry.industry_name)
        .join(Company, Company.industry_id == Industry.industry_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(
            Alumni.validation_status == ValidationStatus.validated,
            CareerRecord.is_current.is_(True),
        )
        .distinct()
        .order_by(Industry.industry_name)
    ).all()
    opts.industries = [
        {"industry_id": r.industry_id, "industry_name": r.industry_name} for r in ind_rows
    ]

    # Companies with a current career record of a validated alumnus
    co_rows = session.execute(
        sa.select(Company.company_id, Company.canonical_name)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(
            Alumni.validation_status == ValidationStatus.validated,
            CareerRecord.is_current.is_(True),
        )
        .distinct()
        .order_by(Company.canonical_name)
    ).all()
    opts.companies = [
        {"company_id": r.company_id, "canonical_name": r.canonical_name} for r in co_rows
    ]

    # Countries from Company → Location join (current career, validated alumni)
    loc_rows = session.scalars(
        sa.select(Location.country)
        .join(Company, Company.location_id == Location.location_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(
            Alumni.validation_status == ValidationStatus.validated,
            CareerRecord.is_current.is_(True),
        )
        .distinct()
        .order_by(Location.country)
    ).all()
    opts.countries = list(loc_rows)

    # All snapshots (quarters) — always show full list regardless of filter
    snap_rows = session.execute(
        sa.select(RefreshSnapshot.snapshot_id, RefreshSnapshot.quarter_label).order_by(
            RefreshSnapshot.quarter_label
        )
    ).all()
    opts.snapshots = [
        {"snapshot_id": r.snapshot_id, "quarter_label": r.quarter_label} for r in snap_rows
    ]

    return opts


# ---------------------------------------------------------------------------
# P5.3 — Executive Overview
# ---------------------------------------------------------------------------


@dataclass
class OverviewResult:
    total_alumni: int = 0
    total_companies: int = 0
    total_industries: int = 0
    total_countries: int = 0
    alumni_by_program: list[dict[str, object]] = field(default_factory=list)
    alumni_by_graduation_year: list[dict[str, object]] = field(default_factory=list)


def get_overview(filters: AnalyticsFilters, session: Session) -> OverviewResult:
    """Executive overview counts (P5.3).

    Counts are scoped to validated alumni.  Company / industry / country counts
    are derived from current career records only.
    """
    result = OverviewResult()
    alumni_where = build_alumni_where(filters)

    # Total validated alumni (after program/year filters)
    result.total_alumni = (
        session.scalar(sa.select(sa.func.count()).select_from(Alumni).where(*alumni_where)) or 0
    )

    # Alumni by program
    prog_rows = session.execute(
        sa.select(
            StudyProgram.program_name,
            sa.func.count(Alumni.alumni_id).label("count"),
        )
        .join(Alumni, Alumni.study_program_id == StudyProgram.program_id)
        .where(*alumni_where)
        .group_by(StudyProgram.program_name)
        .order_by(sa.desc("count"))
    ).all()
    result.alumni_by_program = [
        {"program_name": r.program_name, "count": r.count} for r in prog_rows
    ]

    # Alumni by graduation year
    year_rows = session.execute(
        sa.select(
            Alumni.graduation_year,
            sa.func.count(Alumni.alumni_id).label("count"),
        )
        .where(*alumni_where)
        .group_by(Alumni.graduation_year)
        .order_by(Alumni.graduation_year)
    ).all()
    result.alumni_by_graduation_year = [
        {"graduation_year": r.graduation_year, "count": r.count} for r in year_rows
    ]

    # Distinct companies / industries / countries from current career records.
    # Use COUNT(DISTINCT ...) in SQL rather than loading all IDs into Python.
    career_where = build_career_where(filters)
    country_clause = build_country_clause(filters)
    if country_clause is not None:
        career_where = [*career_where, country_clause]

    base_career = (
        sa.select(Company.company_id, Company.industry_id, Company.location_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(*career_where)
        .subquery("base_career")
    )

    result.total_companies = (
        session.scalar(sa.select(sa.func.count(sa.distinct(base_career.c.company_id)))) or 0
    )

    result.total_industries = (
        session.scalar(
            sa.select(sa.func.count(sa.distinct(base_career.c.industry_id))).where(
                base_career.c.industry_id.is_not(None)
            )
        )
        or 0
    )

    result.total_countries = (
        session.scalar(
            sa.select(sa.func.count(sa.distinct(Location.country))).join(
                base_career, base_career.c.location_id == Location.location_id
            )
        )
        or 0
    )

    return result


# ---------------------------------------------------------------------------
# P5.4 — Career Outcomes
# ---------------------------------------------------------------------------


@dataclass
class CareerOutcomesResult:
    total_validated: int = 0
    employed_count: int = 0
    not_reported_count: int = 0
    seniority_distribution: list[dict[str, object]] = field(default_factory=list)
    top_roles: list[dict[str, object]] = field(default_factory=list)


def get_career_outcomes(filters: AnalyticsFilters, session: Session) -> CareerOutcomesResult:
    """Career outcomes with Employed-vs-Not-Reported semantics (P5.4, D-048).

    "Employed" = validated alumnus has a current CareerRecord.
    "Not Reported" = validated alumnus has no current CareerRecord.
    We never assert an unemployment rate.
    """
    result = CareerOutcomesResult()
    alumni_where = build_alumni_where(filters)

    result.total_validated = (
        session.scalar(sa.select(sa.func.count()).select_from(Alumni).where(*alumni_where)) or 0
    )

    # Alumni IDs with a current career record (optionally filtered by career dims)
    career_where = build_career_where(filters)
    country_clause = build_country_clause(filters)
    if country_clause is not None:
        career_where = [*career_where, country_clause]

    employed_ids_subq = (
        sa.select(CareerRecord.alumni_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .join(Company, Company.company_id == CareerRecord.company_id)
        .where(*career_where)
        .distinct()
        .subquery()
    )

    result.employed_count = (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(Alumni)
            .where(
                *alumni_where,
                Alumni.alumni_id.in_(sa.select(employed_ids_subq.c.alumni_id)),
            )
        )
        or 0
    )

    result.not_reported_count = result.total_validated - result.employed_count

    # Seniority distribution (current roles only, validated alumni)
    sen_rows = session.execute(
        sa.select(
            sa.func.coalesce(CareerRecord.seniority, "Unknown").label("seniority"),
            sa.func.count(CareerRecord.career_record_id).label("count"),
        )
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .join(Company, Company.company_id == CareerRecord.company_id)
        .where(*career_where)
        .group_by("seniority")
        .order_by(sa.desc("count"))
    ).all()
    result.seniority_distribution = [{"seniority": r.seniority, "count": r.count} for r in sen_rows]

    # Top role titles
    role_rows = session.execute(
        sa.select(
            CareerRecord.role_title,
            sa.func.count(CareerRecord.career_record_id).label("count"),
        )
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .join(Company, Company.company_id == CareerRecord.company_id)
        .where(*career_where)
        .group_by(CareerRecord.role_title)
        .order_by(sa.desc("count"))
        .limit(20)
    ).all()
    result.top_roles = [{"role_title": r.role_title, "count": r.count} for r in role_rows]

    return result


# ---------------------------------------------------------------------------
# P5.5 — Company Analytics
# ---------------------------------------------------------------------------


@dataclass
class CompanyAnalyticsResult:
    total_employers: int = 0
    top_employers: list[dict[str, object]] = field(default_factory=list)


def get_company_analytics(filters: AnalyticsFilters, session: Session) -> CompanyAnalyticsResult:
    """Top employers by headcount of current validated employees (P5.5)."""
    result = CompanyAnalyticsResult()
    career_where = build_career_where(filters)
    country_clause = build_country_clause(filters)
    if country_clause is not None:
        career_where = [*career_where, country_clause]

    rows = session.execute(
        sa.select(
            Company.company_id,
            Company.canonical_name,
            sa.func.count(CareerRecord.career_record_id).label("headcount"),
        )
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(*career_where)
        .group_by(Company.company_id, Company.canonical_name)
        .order_by(sa.desc("headcount"))
        .limit(50)
    ).all()

    result.total_employers = (
        session.scalar(
            sa.select(sa.func.count(sa.distinct(CareerRecord.company_id)))
            .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
            .join(Company, Company.company_id == CareerRecord.company_id)
            .where(*career_where)
        )
        or 0
    )

    result.top_employers = [
        {"company_id": r.company_id, "canonical_name": r.canonical_name, "headcount": r.headcount}
        for r in rows
    ]
    return result


# ---------------------------------------------------------------------------
# P5.6 — Industry Analytics
# ---------------------------------------------------------------------------


@dataclass
class IndustryAnalyticsResult:
    industry_distribution: list[dict[str, object]] = field(default_factory=list)
    sector_breakdown: list[dict[str, object]] = field(default_factory=list)


def get_industry_analytics(filters: AnalyticsFilters, session: Session) -> IndustryAnalyticsResult:
    """Industry distribution (industry_name) + sector breakdown (sector_name) (P5.6, D-042)."""
    result = IndustryAnalyticsResult()
    career_where = build_career_where(filters)
    country_clause = build_country_clause(filters)
    if country_clause is not None:
        career_where = [*career_where, country_clause]

    # Industry-level distribution
    ind_rows = session.execute(
        sa.select(
            Industry.industry_id,
            Industry.industry_name,
            Industry.sector_name,
            sa.func.count(CareerRecord.career_record_id).label("count"),
        )
        .join(Company, Company.industry_id == Industry.industry_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(*career_where)
        .group_by(Industry.industry_id, Industry.industry_name, Industry.sector_name)
        .order_by(sa.desc("count"))
    ).all()
    result.industry_distribution = [
        {
            "industry_id": r.industry_id,
            "industry_name": r.industry_name,
            "sector_name": r.sector_name,
            "count": r.count,
        }
        for r in ind_rows
    ]

    # Sector-level rollup — use tuple index to avoid mypy confusion with builtin `count`
    sector_totals: dict[str, int] = defaultdict(int)
    for r in ind_rows:
        sector_totals[r.sector_name] += r[3]  # index 3 = count label
    result.sector_breakdown = [
        {"sector_name": k, "count": v}
        for k, v in sorted(sector_totals.items(), key=lambda x: -x[1])
    ]

    return result


# ---------------------------------------------------------------------------
# P5.7 — Geographic Analytics
# ---------------------------------------------------------------------------


@dataclass
class GeographicAnalyticsResult:
    country_distribution: list[dict[str, object]] = field(default_factory=list)
    city_distribution: list[dict[str, object]] = field(default_factory=list)


def get_geographic_analytics(
    filters: AnalyticsFilters, session: Session
) -> GeographicAnalyticsResult:
    """Country and city distribution of validated alumni (P5.7)."""
    result = GeographicAnalyticsResult()
    career_where = build_career_where(filters)

    # Apply country filter if given
    country_clauses = list(career_where)
    if filters.country is not None:
        country_clauses.append(Location.country == filters.country)

    country_rows = session.execute(
        sa.select(
            Location.country,
            sa.func.count(CareerRecord.career_record_id).label("count"),
        )
        .join(Company, Company.location_id == Location.location_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(*country_clauses)
        .group_by(Location.country)
        .order_by(sa.desc("count"))
    ).all()
    result.country_distribution = [{"country": r.country, "count": r.count} for r in country_rows]

    city_rows = session.execute(
        sa.select(
            Location.country,
            Location.city,
            sa.func.count(CareerRecord.career_record_id).label("count"),
        )
        .join(Company, Company.location_id == Location.location_id)
        .join(CareerRecord, CareerRecord.company_id == Company.company_id)
        .join(Alumni, Alumni.alumni_id == CareerRecord.alumni_id)
        .where(*country_clauses, Location.city.is_not(None))
        .group_by(Location.country, Location.city)
        .order_by(sa.desc("count"))
        .limit(50)
    ).all()
    result.city_distribution = [
        {"country": r.country, "city": r.city, "count": r.count} for r in city_rows
    ]

    return result


# ---------------------------------------------------------------------------
# P5.8 — Alumni Directory
# ---------------------------------------------------------------------------

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


@dataclass
class AlumniDirectoryItem:
    alumni_id: int
    public_id: str
    full_name: str
    study_program_id: int
    program_name: str
    graduation_year: int
    validation_status: str
    current_company: str | None
    current_role: str | None
    current_seniority: str | None


@dataclass
class AlumniDirectoryResult:
    total: int = 0
    page: int = 1
    page_size: int = _DEFAULT_PAGE_SIZE
    items: list[AlumniDirectoryItem] = field(default_factory=list)


def get_alumni_directory(
    filters: AnalyticsFilters,
    session: Session,
    search: str | None = None,
    page: int = 1,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> AlumniDirectoryResult:
    """Paginated, filterable, searchable alumni directory (P5.8).

    Only validated alumni are returned (D-047).
    search performs a case-insensitive substring match on full_name.
    """
    page_size = min(max(1, page_size), _MAX_PAGE_SIZE)
    page = max(1, page)
    offset = (page - 1) * page_size

    alumni_where = build_alumni_where(filters)
    if search:
        alumni_where = list(alumni_where) + [Alumni.full_name.ilike(f"%{search}%")]

    # Career-record correlated subquery for current role
    cr_alias = (
        sa.select(
            CareerRecord.alumni_id,
            CareerRecord.company_id,
            CareerRecord.role_title,
            CareerRecord.seniority,
        )
        .where(CareerRecord.is_current.is_(True))
        .subquery("current_career")
    )

    stmt = (
        sa.select(
            Alumni.alumni_id,
            Alumni.public_id,
            Alumni.full_name,
            Alumni.study_program_id,
            StudyProgram.program_name,
            Alumni.graduation_year,
            Alumni.validation_status,
            Company.canonical_name.label("current_company"),
            cr_alias.c.role_title.label("current_role"),
            cr_alias.c.seniority.label("current_seniority"),
        )
        .join(StudyProgram, StudyProgram.program_id == Alumni.study_program_id)
        .outerjoin(cr_alias, cr_alias.c.alumni_id == Alumni.alumni_id)
        .outerjoin(Company, Company.company_id == cr_alias.c.company_id)
        .where(*alumni_where)
    )

    # Apply career-level filters via EXISTS subquery to avoid row multiplication
    if filters.company_id is not None:
        stmt = stmt.where(cr_alias.c.company_id == filters.company_id)
    if filters.industry_id is not None:
        stmt = stmt.where(Company.industry_id == filters.industry_id)
    if filters.snapshot_id is not None:
        pass  # snapshot filter not directly applicable to directory outer-join path
    if filters.country is not None:
        loc_subq = (
            sa.select(Company.company_id)
            .join(Location, Location.location_id == Company.location_id)
            .where(Location.country == filters.country)
            .subquery()
        )
        stmt = stmt.where(cr_alias.c.company_id.in_(sa.select(loc_subq.c.company_id)))

    count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
    total = session.scalar(count_stmt) or 0

    rows = session.execute(stmt.order_by(Alumni.full_name).offset(offset).limit(page_size)).all()

    items = [
        AlumniDirectoryItem(
            alumni_id=r.alumni_id,
            public_id=r.public_id,
            full_name=r.full_name,
            study_program_id=r.study_program_id,
            program_name=r.program_name,
            graduation_year=r.graduation_year,
            validation_status=r.validation_status,
            current_company=r.current_company,
            current_role=r.current_role,
            current_seniority=r.current_seniority,
        )
        for r in rows
    ]

    return AlumniDirectoryResult(total=total, page=page, page_size=page_size, items=items)


# ---------------------------------------------------------------------------
# P6.10 — Alumnus Detail (profile + full career history, snapshot-aware)
# ---------------------------------------------------------------------------


@dataclass
class CareerHistoryEntry:
    career_record_id: int
    company_name: str
    role_title: str
    seniority: str | None
    is_current: bool
    snapshot_label: str | None
    captured_on: str | None


@dataclass
class AlumnusDetail:
    alumni_id: int
    public_id: str
    full_name: str
    university: str
    program_name: str
    graduation_year: int
    linkedin_url: str | None
    validation_status: str
    career_history: list[CareerHistoryEntry]


def get_alumnus_detail(alumni_id: int, session: Session) -> AlumnusDetail | None:
    """Return profile + full career history for a single validated alumnus (P6.10).

    Returns None when the alumnus does not exist or is not validated (D-047).
    Career records are returned newest-first (is_current first, then by
    career_record_id descending as a stable proxy for insertion order).
    """
    alumni_row = session.execute(
        sa.select(
            Alumni.alumni_id,
            Alumni.public_id,
            Alumni.full_name,
            Alumni.university,
            Alumni.graduation_year,
            Alumni.linkedin_url,
            Alumni.validation_status,
            StudyProgram.program_name,
        )
        .join(StudyProgram, StudyProgram.program_id == Alumni.study_program_id)
        .where(
            Alumni.alumni_id == alumni_id,
            Alumni.validation_status == ValidationStatus.validated,
        )
    ).one_or_none()

    if alumni_row is None:
        return None

    career_rows = session.execute(
        sa.select(
            CareerRecord.career_record_id,
            CareerRecord.role_title,
            CareerRecord.seniority,
            CareerRecord.is_current,
            CareerRecord.captured_on,
            Company.canonical_name.label("company_name"),
            RefreshSnapshot.quarter_label.label("snapshot_label"),
        )
        .join(Company, Company.company_id == CareerRecord.company_id)
        .outerjoin(RefreshSnapshot, RefreshSnapshot.snapshot_id == CareerRecord.snapshot_id)
        .where(CareerRecord.alumni_id == alumni_id)
        .order_by(
            sa.desc(CareerRecord.is_current),
            sa.desc(CareerRecord.career_record_id),
        )
    ).all()

    history = [
        CareerHistoryEntry(
            career_record_id=r.career_record_id,
            company_name=r.company_name,
            role_title=r.role_title,
            seniority=r.seniority,
            is_current=r.is_current,
            snapshot_label=r.snapshot_label,
            captured_on=str(r.captured_on) if r.captured_on else None,
        )
        for r in career_rows
    ]

    return AlumnusDetail(
        alumni_id=alumni_row.alumni_id,
        public_id=alumni_row.public_id,
        full_name=alumni_row.full_name,
        university=alumni_row.university,
        program_name=alumni_row.program_name,
        graduation_year=alumni_row.graduation_year,
        linkedin_url=alumni_row.linkedin_url,
        validation_status=alumni_row.validation_status,
        career_history=history,
    )
