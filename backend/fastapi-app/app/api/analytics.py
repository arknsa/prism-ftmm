"""Analytics API endpoints (P5.2–P5.8).

All endpoints are read-only and require the `analytics:read` permission.
Filters are passed as query parameters and mapped to AnalyticsFilters.

Route prefix: /api/v1/analytics
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.schemas.analytics import (
    AlumniDirectoryOut,
    AlumnusDetailOut,
    CareerOutcomesOut,
    CompanyAnalyticsOut,
    FilterOptionsOut,
    GeographicAnalyticsOut,
    IndustryAnalyticsOut,
    OverviewOut,
)
from app.services.analytics import (
    get_alumni_directory,
    get_alumnus_detail,
    get_career_outcomes,
    get_company_analytics,
    get_filter_options,
    get_geographic_analytics,
    get_industry_analytics,
    get_overview,
)
from app.services.analytics_filters import AnalyticsFilters

router = APIRouter(prefix="/api/v1", tags=["analytics"])


# ---------------------------------------------------------------------------
# Shared filter query params dependency
# ---------------------------------------------------------------------------


def _parse_filters(
    study_program_id: Annotated[int | None, Query()] = None,
    graduation_year: Annotated[int | None, Query()] = None,
    industry_id: Annotated[int | None, Query()] = None,
    company_id: Annotated[int | None, Query()] = None,
    country: Annotated[str | None, Query(max_length=100)] = None,
    snapshot_id: Annotated[int | None, Query()] = None,
) -> AnalyticsFilters:
    return AnalyticsFilters(
        study_program_id=study_program_id,
        graduation_year=graduation_year,
        industry_id=industry_id,
        company_id=company_id,
        country=country,
        snapshot_id=snapshot_id,
    )


# ---------------------------------------------------------------------------
# P5.2 — Filter options
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/filter-options",
    response_model=FilterOptionsOut,
    summary="Filter options",
)
def filter_options(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    opts = get_filter_options(session)
    return {
        "programs": [
            {"program_id": p["program_id"], "program_name": p["program_name"]}
            for p in opts.programs
        ],
        "graduation_years": opts.graduation_years,
        "industries": [
            {"industry_id": i["industry_id"], "industry_name": i["industry_name"]}
            for i in opts.industries
        ],
        "companies": [
            {"company_id": c["company_id"], "canonical_name": c["canonical_name"]}
            for c in opts.companies
        ],
        "countries": opts.countries,
        "snapshots": [
            {"snapshot_id": s["snapshot_id"], "quarter_label": s["quarter_label"]}
            for s in opts.snapshots
        ],
    }


# ---------------------------------------------------------------------------
# P5.3 — Executive Overview
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/overview",
    response_model=OverviewOut,
    summary="Executive overview",
)
def overview(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
) -> dict[str, object]:
    r = get_overview(filters, session)
    return {
        "total_alumni": r.total_alumni,
        "total_companies": r.total_companies,
        "total_industries": r.total_industries,
        "total_countries": r.total_countries,
        "alumni_by_program": r.alumni_by_program,
        "alumni_by_graduation_year": r.alumni_by_graduation_year,
    }


# ---------------------------------------------------------------------------
# P5.4 — Career Outcomes
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/career-outcomes",
    response_model=CareerOutcomesOut,
    summary="Career outcomes (Employed vs Not Reported)",
)
def career_outcomes(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
) -> dict[str, object]:
    r = get_career_outcomes(filters, session)
    return {
        "total_validated": r.total_validated,
        "employed_count": r.employed_count,
        "not_reported_count": r.not_reported_count,
        "seniority_distribution": r.seniority_distribution,
        "top_roles": r.top_roles,
    }


# ---------------------------------------------------------------------------
# P5.5 — Company Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/companies",
    response_model=CompanyAnalyticsOut,
    summary="Company analytics (top employers)",
)
def company_analytics(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
) -> dict[str, object]:
    r = get_company_analytics(filters, session)
    return {
        "total_employers": r.total_employers,
        "top_employers": r.top_employers,
    }


# ---------------------------------------------------------------------------
# P5.6 — Industry Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/industries",
    response_model=IndustryAnalyticsOut,
    summary="Industry analytics (distribution + sector breakdown)",
)
def industry_analytics(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
) -> dict[str, object]:
    r = get_industry_analytics(filters, session)
    return {
        "industry_distribution": r.industry_distribution,
        "sector_breakdown": r.sector_breakdown,
    }


# ---------------------------------------------------------------------------
# P5.7 — Geographic Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/geography",
    response_model=GeographicAnalyticsOut,
    summary="Geographic analytics (country + city distribution)",
)
def geographic_analytics(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
) -> dict[str, object]:
    r = get_geographic_analytics(filters, session)
    return {
        "country_distribution": r.country_distribution,
        "city_distribution": r.city_distribution,
    }


# ---------------------------------------------------------------------------
# P5.8 — Alumni Directory
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/directory",
    response_model=AlumniDirectoryOut,
    summary="Alumni directory (paginated, filterable, searchable)",
)
def alumni_directory(
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
    filters: Annotated[AnalyticsFilters, Depends(_parse_filters)],
    search: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    r = get_alumni_directory(filters, session, search=search, page=page, page_size=page_size)
    return {
        "total": r.total,
        "page": r.page,
        "page_size": r.page_size,
        "items": [
            {
                "alumni_id": item.alumni_id,
                "public_id": item.public_id,
                "full_name": item.full_name,
                "study_program_id": item.study_program_id,
                "program_name": item.program_name,
                "graduation_year": item.graduation_year,
                "validation_status": item.validation_status,
                "current_company": item.current_company,
                "current_role": item.current_role,
                "current_seniority": item.current_seniority,
            }
            for item in r.items
        ],
    }


# ---------------------------------------------------------------------------
# P6.10 — Alumnus Detail
# ---------------------------------------------------------------------------


@router.get(
    "/analytics/alumni/{alumni_id}",
    response_model=AlumnusDetailOut,
    summary="Alumnus profile + career history (snapshot-aware)",
)
def alumnus_detail(
    alumni_id: int,
    _: Annotated[None, Depends(require_permission("analytics:read"))],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    detail = get_alumnus_detail(alumni_id, session)
    if detail is None:
        raise HTTPException(status_code=404, detail="Alumni not found or not validated.")
    return {
        "alumni_id": detail.alumni_id,
        "public_id": detail.public_id,
        "full_name": detail.full_name,
        "university": detail.university,
        "program_name": detail.program_name,
        "graduation_year": detail.graduation_year,
        "linkedin_url": detail.linkedin_url,
        "validation_status": detail.validation_status,
        "career_history": [
            {
                "career_record_id": e.career_record_id,
                "company_name": e.company_name,
                "role_title": e.role_title,
                "seniority": e.seniority,
                "is_current": e.is_current,
                "snapshot_label": e.snapshot_label,
                "captured_on": e.captured_on,
            }
            for e in detail.career_history
        ],
    }
