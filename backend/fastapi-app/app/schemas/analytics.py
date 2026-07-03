"""Pydantic response schemas for analytics endpoints (P5.2–P5.8)."""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# P5.2 — Filter options
# ---------------------------------------------------------------------------


class ProgramOption(BaseModel):
    program_id: int
    program_name: str


class IndustryOption(BaseModel):
    industry_id: int
    industry_name: str


class CompanyOption(BaseModel):
    company_id: int
    canonical_name: str


class SnapshotOption(BaseModel):
    snapshot_id: int
    quarter_label: str


class FilterOptionsOut(BaseModel):
    programs: list[ProgramOption]
    graduation_years: list[int]
    industries: list[IndustryOption]
    companies: list[CompanyOption]
    countries: list[str]
    snapshots: list[SnapshotOption]


# ---------------------------------------------------------------------------
# P5.3 — Executive Overview
# ---------------------------------------------------------------------------


class ProgramCount(BaseModel):
    program_name: str
    count: int


class YearCount(BaseModel):
    graduation_year: int
    count: int


class OverviewOut(BaseModel):
    total_alumni: int
    total_companies: int
    total_industries: int
    total_countries: int
    alumni_by_program: list[ProgramCount]
    alumni_by_graduation_year: list[YearCount]


# ---------------------------------------------------------------------------
# P5.4 — Career Outcomes
# ---------------------------------------------------------------------------


class SeniorityCount(BaseModel):
    seniority: str
    count: int


class RoleCount(BaseModel):
    role_title: str
    count: int


class CareerOutcomesOut(BaseModel):
    total_validated: int
    employed_count: int
    not_reported_count: int
    seniority_distribution: list[SeniorityCount]
    top_roles: list[RoleCount]


# ---------------------------------------------------------------------------
# P5.5 — Company Analytics
# ---------------------------------------------------------------------------


class EmployerHeadcount(BaseModel):
    company_id: int
    canonical_name: str
    headcount: int


class CompanyAnalyticsOut(BaseModel):
    total_employers: int
    top_employers: list[EmployerHeadcount]


# ---------------------------------------------------------------------------
# P5.6 — Industry Analytics
# ---------------------------------------------------------------------------


class IndustryCount(BaseModel):
    industry_id: int
    industry_name: str
    sector_name: str
    count: int


class SectorCount(BaseModel):
    sector_name: str
    count: int


class IndustryAnalyticsOut(BaseModel):
    industry_distribution: list[IndustryCount]
    sector_breakdown: list[SectorCount]


# ---------------------------------------------------------------------------
# P5.7 — Geographic Analytics
# ---------------------------------------------------------------------------


class CountryCount(BaseModel):
    country: str
    count: int


class CityCount(BaseModel):
    country: str
    city: str
    count: int


class GeographicAnalyticsOut(BaseModel):
    country_distribution: list[CountryCount]
    city_distribution: list[CityCount]


# ---------------------------------------------------------------------------
# P5.8 — Alumni Directory
# ---------------------------------------------------------------------------


class AlumniDirectoryItemOut(BaseModel):
    alumni_id: int
    public_id: str
    full_name: str
    study_program_id: int
    program_name: str
    graduation_year: int
    validation_status: str
    current_company: str | None = None
    current_role: str | None = None
    current_seniority: str | None = None


class AlumniDirectoryOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AlumniDirectoryItemOut]


# ---------------------------------------------------------------------------
# P6.10 — Alumnus detail
# ---------------------------------------------------------------------------


class CareerHistoryEntryOut(BaseModel):
    career_record_id: int
    company_name: str
    role_title: str
    seniority: str | None = None
    is_current: bool
    snapshot_label: str | None = None
    captured_on: str | None = None


class AlumnusDetailOut(BaseModel):
    alumni_id: int
    public_id: str
    full_name: str
    university: str
    program_name: str
    graduation_year: int
    linkedin_url: str | None = None
    validation_status: str
    career_history: list[CareerHistoryEntryOut]
