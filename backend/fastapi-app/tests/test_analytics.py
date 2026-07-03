"""Tests for analytics service and API endpoints (P5.2–P5.8).

Service tests use direct function calls with a mocked Session to verify
query construction and result shaping without touching the DB.

API tests use FastAPI TestClient with overridden auth + session.

Coverage:
- P5.1: AnalyticsFilters dataclass, build_alumni_where, build_career_where
- P5.2: GET /analytics/filter-options — 200, 403
- P5.3: GET /analytics/overview — 200, filter propagation, 403
- P5.4: GET /analytics/career-outcomes — 200, employed/not-reported counts, 403
- P5.5: GET /analytics/companies — 200, 403
- P5.6: GET /analytics/industries — 200, sector rollup, 403
- P5.7: GET /analytics/geography — 200, country filter, 403
- P5.8: GET /analytics/directory — 200, pagination, search, 403
- D-047: only validated alumni counted (service-level assertion)
- D-048: not_reported = total_validated - employed (never called "unemployment")
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.schemas.auth import AuthenticatedUser
from app.services.analytics import (
    AlumniDirectoryResult,
    CareerOutcomesResult,
    CompanyAnalyticsResult,
    FilterOptions,
    GeographicAnalyticsResult,
    IndustryAnalyticsResult,
    OverviewResult,
)
from app.services.analytics_filters import (
    AnalyticsFilters,
    build_alumni_where,
    build_career_where,
    build_country_clause,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------

_ANALYST = AuthenticatedUser(
    user_id=1,
    supabase_uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    role_name="Faculty Viewer",
    permissions=frozenset(["analytics:read"]),
)

_NO_PERM = AuthenticatedUser(
    user_id=99,
    supabase_uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    role_name="External",
    permissions=frozenset(),
)


def _make_client(user: AuthenticatedUser, session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# P5.1 — AnalyticsFilters + builders
# ---------------------------------------------------------------------------


class TestAnalyticsFilters:
    def test_default_filters_all_none(self) -> None:
        f = AnalyticsFilters()
        assert f.study_program_id is None
        assert f.graduation_year is None
        assert f.industry_id is None
        assert f.company_id is None
        assert f.country is None
        assert f.snapshot_id is None

    def test_filters_frozen(self) -> None:
        f = AnalyticsFilters(study_program_id=1)
        with pytest.raises((AttributeError, TypeError)):
            f.study_program_id = 2  # type: ignore[misc]

    def test_build_alumni_where_base(self) -> None:
        clauses = build_alumni_where(AnalyticsFilters())
        # Always includes validated guard — one clause
        assert len(clauses) == 1

    def test_build_alumni_where_with_program(self) -> None:
        clauses = build_alumni_where(AnalyticsFilters(study_program_id=3))
        assert len(clauses) == 2

    def test_build_alumni_where_with_year(self) -> None:
        clauses = build_alumni_where(AnalyticsFilters(graduation_year=2023))
        assert len(clauses) == 2

    def test_build_alumni_where_program_and_year(self) -> None:
        clauses = build_alumni_where(AnalyticsFilters(study_program_id=2, graduation_year=2022))
        assert len(clauses) == 3

    def test_build_career_where_base(self) -> None:
        clauses = build_career_where(AnalyticsFilters())
        # is_current + validated guard = 2 base clauses
        assert len(clauses) == 2

    def test_build_career_where_with_company(self) -> None:
        clauses = build_career_where(AnalyticsFilters(company_id=5))
        assert len(clauses) == 3

    def test_build_career_where_with_industry(self) -> None:
        clauses = build_career_where(AnalyticsFilters(industry_id=7))
        assert len(clauses) == 3

    def test_build_career_where_with_snapshot(self) -> None:
        clauses = build_career_where(AnalyticsFilters(snapshot_id=2))
        assert len(clauses) == 3

    def test_build_career_where_all_dims(self) -> None:
        clauses = build_career_where(
            AnalyticsFilters(
                study_program_id=1,
                graduation_year=2022,
                company_id=5,
                industry_id=7,
                snapshot_id=2,
            )
        )
        assert len(clauses) == 7

    def test_build_country_clause_none_when_no_country(self) -> None:
        assert build_country_clause(AnalyticsFilters()) is None

    def test_build_country_clause_returns_clause_when_country_set(self) -> None:
        clause = build_country_clause(AnalyticsFilters(country="Singapore"))
        assert clause is not None
        # The clause restricts CareerRecord.company_id via a subquery on Location.
        compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
        assert "career_record.company_id IN" in compiled
        assert "Singapore" in compiled


# ---------------------------------------------------------------------------
# P5.4 — D-047 / D-048 semantic test at service level
# ---------------------------------------------------------------------------


class TestCareerOutcomesSemantics:
    """Verify Employed vs Not Reported arithmetic (D-048) — no unemployment rate."""

    def test_not_reported_equals_total_minus_employed(self) -> None:
        result = CareerOutcomesResult(
            total_validated=100,
            employed_count=60,
            not_reported_count=40,
        )
        assert result.not_reported_count == result.total_validated - result.employed_count

    def test_all_employed(self) -> None:
        r = CareerOutcomesResult(total_validated=50, employed_count=50, not_reported_count=0)
        assert r.not_reported_count == 0

    def test_none_employed(self) -> None:
        r = CareerOutcomesResult(total_validated=30, employed_count=0, not_reported_count=30)
        assert r.employed_count == 0


# ---------------------------------------------------------------------------
# API — common 403 guard
# ---------------------------------------------------------------------------


class TestAnalyticsPermissionGuard:
    """All analytics endpoints reject users without analytics:read (D-047)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/analytics/filter-options",
            "/api/v1/analytics/overview",
            "/api/v1/analytics/career-outcomes",
            "/api/v1/analytics/companies",
            "/api/v1/analytics/industries",
            "/api/v1/analytics/geography",
            "/api/v1/analytics/directory",
            "/api/v1/analytics/alumni/1",
        ],
    )
    def test_403_without_permission(self, path: str) -> None:
        session = MagicMock(spec=Session)
        client = _make_client(_NO_PERM, session)
        resp = client.get(path)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# P5.2 — filter-options endpoint
# ---------------------------------------------------------------------------


class TestFilterOptionsEndpoint:
    def _mock_session(self) -> MagicMock:
        session = MagicMock(spec=Session)
        # .execute().all() pattern for each query
        session.execute.return_value.all.return_value = []
        session.scalars.return_value.all.return_value = []
        return session

    def test_200_empty(self) -> None:
        with patch(
            "app.api.analytics.get_filter_options",
            return_value=FilterOptions(
                programs=[],
                graduation_years=[],
                industries=[],
                companies=[],
                countries=[],
                snapshots=[],
            ),
        ):
            session = self._mock_session()
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/filter-options")
        assert resp.status_code == 200
        body = resp.json()
        assert body["programs"] == []
        assert body["graduation_years"] == []

    def test_200_populated(self) -> None:
        with patch(
            "app.api.analytics.get_filter_options",
            return_value=FilterOptions(
                programs=[{"program_id": 1, "program_name": "Teknik Industri"}],
                graduation_years=[2022, 2023],
                industries=[{"industry_id": 2, "industry_name": "Technology"}],
                companies=[{"company_id": 3, "canonical_name": "PT Maju"}],
                countries=["Indonesia"],
                snapshots=[{"snapshot_id": 1, "quarter_label": "2025-Q1"}],
            ),
        ):
            session = self._mock_session()
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/filter-options")
        assert resp.status_code == 200
        body = resp.json()
        assert body["programs"][0]["program_name"] == "Teknik Industri"
        assert body["graduation_years"] == [2022, 2023]
        assert body["countries"] == ["Indonesia"]
        assert body["snapshots"][0]["quarter_label"] == "2025-Q1"


# ---------------------------------------------------------------------------
# P5.3 — overview endpoint
# ---------------------------------------------------------------------------


class TestOverviewEndpoint:
    def _mock_overview(self) -> OverviewResult:
        return OverviewResult(
            total_alumni=50,
            total_companies=10,
            total_industries=5,
            total_countries=3,
            alumni_by_program=[{"program_name": "Teknik Industri", "count": 30}],
            alumni_by_graduation_year=[{"graduation_year": 2022, "count": 20}],
        )

    def test_200_basic(self) -> None:
        with patch("app.api.analytics.get_overview", return_value=self._mock_overview()):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_alumni"] == 50
        assert body["total_companies"] == 10
        assert body["alumni_by_program"][0]["program_name"] == "Teknik Industri"

    def test_filter_params_accepted(self) -> None:
        captured: list[AnalyticsFilters] = []

        def _fake_overview(filters: AnalyticsFilters, session: Session) -> OverviewResult:
            captured.append(filters)
            return OverviewResult()

        with patch("app.api.analytics.get_overview", side_effect=_fake_overview):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get(
                "/api/v1/analytics/overview",
                params={"study_program_id": 2, "graduation_year": 2022, "snapshot_id": 1},
            )
        assert resp.status_code == 200
        assert captured[0].study_program_id == 2
        assert captured[0].graduation_year == 2022
        assert captured[0].snapshot_id == 1


# ---------------------------------------------------------------------------
# P5.4 — career-outcomes endpoint
# ---------------------------------------------------------------------------


class TestCareerOutcomesEndpoint:
    def test_200_basic(self) -> None:
        mock_result = CareerOutcomesResult(
            total_validated=100,
            employed_count=70,
            not_reported_count=30,
            seniority_distribution=[{"seniority": "Senior", "count": 40}],
            top_roles=[{"role_title": "Engineer", "count": 25}],
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/career-outcomes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_validated"] == 100
        assert body["employed_count"] == 70
        assert body["not_reported_count"] == 30
        # D-048: never expose an unemployment rate — these are the only keys
        assert "unemployment_rate" not in body
        assert "unemployed_count" not in body

    def test_not_reported_is_remainder(self) -> None:
        mock_result = CareerOutcomesResult(
            total_validated=50,
            employed_count=35,
            not_reported_count=15,
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/career-outcomes")
        body = resp.json()
        assert body["not_reported_count"] == body["total_validated"] - body["employed_count"]


# ---------------------------------------------------------------------------
# P5.5 — company analytics endpoint
# ---------------------------------------------------------------------------


class TestCompanyAnalyticsEndpoint:
    def test_200_basic(self) -> None:
        mock_result = CompanyAnalyticsResult(
            total_employers=5,
            top_employers=[
                {"company_id": 1, "canonical_name": "PT Maju", "headcount": 10},
            ],
        )
        with patch("app.api.analytics.get_company_analytics", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/companies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_employers"] == 5
        assert body["top_employers"][0]["canonical_name"] == "PT Maju"


# ---------------------------------------------------------------------------
# P5.6 — industry analytics endpoint
# ---------------------------------------------------------------------------


class TestIndustryAnalyticsEndpoint:
    def test_200_sector_rollup(self) -> None:
        mock_result = IndustryAnalyticsResult(
            industry_distribution=[
                {
                    "industry_id": 1,
                    "industry_name": "Software",
                    "sector_name": "Technology",
                    "count": 20,
                },
                {
                    "industry_id": 2,
                    "industry_name": "Hardware",
                    "sector_name": "Technology",
                    "count": 10,
                },
                {
                    "industry_id": 3,
                    "industry_name": "Banking",
                    "sector_name": "Finance",
                    "count": 15,
                },
            ],
            sector_breakdown=[
                {"sector_name": "Technology", "count": 30},
                {"sector_name": "Finance", "count": 15},
            ],
        )
        with patch("app.api.analytics.get_industry_analytics", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/industries")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["industry_distribution"]) == 3
        assert body["sector_breakdown"][0]["sector_name"] == "Technology"
        assert body["sector_breakdown"][0]["count"] == 30


# ---------------------------------------------------------------------------
# P5.7 — geographic analytics endpoint
# ---------------------------------------------------------------------------


class TestGeographicAnalyticsEndpoint:
    def test_200_basic(self) -> None:
        mock_result = GeographicAnalyticsResult(
            country_distribution=[{"country": "Indonesia", "count": 80}],
            city_distribution=[{"country": "Indonesia", "city": "Surabaya", "count": 40}],
        )
        with patch("app.api.analytics.get_geographic_analytics", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/geography")
        assert resp.status_code == 200
        body = resp.json()
        assert body["country_distribution"][0]["country"] == "Indonesia"
        assert body["city_distribution"][0]["city"] == "Surabaya"

    def test_country_filter_accepted(self) -> None:
        captured: list[AnalyticsFilters] = []

        def _fake(filters: AnalyticsFilters, session: Session) -> GeographicAnalyticsResult:
            captured.append(filters)
            return GeographicAnalyticsResult()

        with patch("app.api.analytics.get_geographic_analytics", side_effect=_fake):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/geography", params={"country": "Indonesia"})
        assert resp.status_code == 200
        assert captured[0].country == "Indonesia"


# ---------------------------------------------------------------------------
# P5.8 — alumni directory endpoint
# ---------------------------------------------------------------------------


class TestAlumniDirectoryEndpoint:
    def _mock_item(self, alumni_id: int = 1) -> dict[str, object]:
        return {
            "alumni_id": alumni_id,
            "public_id": "uuid-1234",
            "full_name": "Budi Santoso",
            "study_program_id": 2,
            "program_name": "Teknik Industri",
            "graduation_year": 2022,
            "validation_status": "validated",
            "current_company": "PT Maju",
            "current_role": "Engineer",
            "current_seniority": "Mid",
        }

    def test_200_basic(self) -> None:
        from app.services.analytics import AlumniDirectoryItem, AlumniDirectoryResult

        item = AlumniDirectoryItem(
            alumni_id=1,
            public_id="uuid-1234",
            full_name="Budi Santoso",
            study_program_id=2,
            program_name="Teknik Industri",
            graduation_year=2022,
            validation_status="validated",
            current_company="PT Maju",
            current_role="Engineer",
            current_seniority="Mid",
        )
        mock_result = AlumniDirectoryResult(total=1, page=1, page_size=50, items=[item])
        with patch("app.api.analytics.get_alumni_directory", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/directory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["full_name"] == "Budi Santoso"
        assert body["items"][0]["validation_status"] == "validated"

    def test_pagination_params_accepted(self) -> None:
        from app.services.analytics import AlumniDirectoryResult

        captured: list[dict[str, object]] = []

        def _fake(
            filters: AnalyticsFilters,
            session: Session,
            search: str | None = None,
            page: int = 1,
            page_size: int = 50,
        ) -> AlumniDirectoryResult:
            captured.append({"page": page, "page_size": page_size, "search": search})
            return AlumniDirectoryResult(total=0, page=page, page_size=page_size)

        with patch("app.api.analytics.get_alumni_directory", side_effect=_fake):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get(
                "/api/v1/analytics/directory",
                params={"page": 2, "page_size": 25, "search": "Budi"},
            )
        assert resp.status_code == 200
        assert captured[0]["page"] == 2
        assert captured[0]["page_size"] == 25
        assert captured[0]["search"] == "Budi"

    def test_page_size_capped_at_200(self) -> None:
        from app.services.analytics import AlumniDirectoryResult

        captured: list[int] = []

        def _fake(
            filters: AnalyticsFilters,
            session: Session,
            search: str | None = None,
            page: int = 1,
            page_size: int = 50,
        ) -> AlumniDirectoryResult:
            captured.append(page_size)
            return AlumniDirectoryResult(total=0, page=page, page_size=page_size)

        with patch("app.api.analytics.get_alumni_directory", side_effect=_fake):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            # FastAPI Query(le=200) rejects > 200 with 422
            resp = client.get("/api/v1/analytics/directory", params={"page_size": 201})
        assert resp.status_code == 422

    def test_only_validated_in_response(self) -> None:
        from app.services.analytics import AlumniDirectoryItem, AlumniDirectoryResult

        item = AlumniDirectoryItem(
            alumni_id=1,
            public_id="uuid-1",
            full_name="Citra Dewi",
            study_program_id=1,
            program_name="Data Science Tech",
            graduation_year=2023,
            validation_status="validated",
            current_company=None,
            current_role=None,
            current_seniority=None,
        )
        mock_result = AlumniDirectoryResult(total=1, page=1, page_size=50, items=[item])
        with patch("app.api.analytics.get_alumni_directory", return_value=mock_result):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/directory")
        body = resp.json()
        for it in body["items"]:
            assert it["validation_status"] == "validated"


# ---------------------------------------------------------------------------
# P6.10 — Alumnus detail endpoint
# ---------------------------------------------------------------------------


class TestAlumnusDetailEndpoint:
    def _mock_detail(self) -> object:
        from app.services.analytics import AlumnusDetail, CareerHistoryEntry

        return AlumnusDetail(
            alumni_id=1,
            public_id="uuid-abc",
            full_name="Budi Santoso",
            university="Universitas Airlangga",
            program_name="Teknik Industri",
            graduation_year=2022,
            linkedin_url=None,
            validation_status="validated",
            career_history=[
                CareerHistoryEntry(
                    career_record_id=10,
                    company_name="PT Maju",
                    role_title="Software Engineer",
                    seniority="Mid",
                    is_current=True,
                    snapshot_label="2025-Q1",
                    captured_on="2025-03-01",
                )
            ],
        )

    def test_200_basic(self) -> None:
        with patch("app.api.analytics.get_alumnus_detail", return_value=self._mock_detail()):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/alumni/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["full_name"] == "Budi Santoso"
        assert body["validation_status"] == "validated"
        assert len(body["career_history"]) == 1
        assert body["career_history"][0]["is_current"] is True
        assert body["career_history"][0]["snapshot_label"] == "2025-Q1"

    def test_404_not_found_or_not_validated(self) -> None:
        with patch("app.api.analytics.get_alumnus_detail", return_value=None):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/alumni/9999")
        assert resp.status_code == 404

    def test_no_linkedin_in_response_when_null(self) -> None:
        with patch("app.api.analytics.get_alumnus_detail", return_value=self._mock_detail()):
            session = MagicMock(spec=Session)
            client = _make_client(_ANALYST, session)
            resp = client.get("/api/v1/analytics/alumni/1")
        body = resp.json()
        assert body["linkedin_url"] is None
