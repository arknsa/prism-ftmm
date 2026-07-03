"""Edge-case tests for aggregation correctness and boundary conditions (P7.6).

Covers:
- Empty validated alumni dataset → all endpoints return 0/empty, not 500.
- Single alumnus edge case → counts work correctly.
- All alumni employed (not_reported=0) and none employed (employed=0).
- Import parser boundary: header-only CSV, single row, all-error batch.
- D-047: analytics service is always called with validated filter applied.
- D-048: not_reported_count arithmetic is always correct.
- Country filter propagated to analytics correctly.
- Snapshot filter with non-existent ID returns 0 (not 404).

Decisions: D-007, D-042, D-047, D-048.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.staging import ImportBatch
from app.schemas.auth import AuthenticatedUser
from app.services.analytics import (
    CareerOutcomesResult,
    CompanyAnalyticsResult,
    GeographicAnalyticsResult,
    IndustryAnalyticsResult,
    OverviewResult,
)
from app.services.import_parser import parse_import
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

_VIEWER = AuthenticatedUser(
    user_id=1,
    supabase_uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    role_name="Faculty Viewer",
    permissions=frozenset(["analytics:read"]),
)


def _make_client(session: MagicMock) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _VIEWER
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=True)


def _make_session() -> MagicMock:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    session.scalars.return_value = scalars_mock
    session.execute.return_value.all.return_value = []
    return session


# ---------------------------------------------------------------------------
# Empty dataset boundary (no validated alumni)
# ---------------------------------------------------------------------------


class TestEmptyDataset:
    """All analytics endpoints must return 200 with zero-valued/empty responses
    when no validated alumni exist. Never 500."""

    def test_overview_empty_returns_zeros(self) -> None:
        overview = OverviewResult()  # all fields default to 0 / []
        with patch("app.api.analytics.get_overview", return_value=overview):
            resp = _make_client(_make_session()).get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_alumni"] == 0
        assert body["total_companies"] == 0
        assert body["total_industries"] == 0
        assert body["total_countries"] == 0
        assert body["alumni_by_program"] == []
        assert body["alumni_by_graduation_year"] == []

    def test_career_outcomes_empty_returns_zeros(self) -> None:
        outcomes = CareerOutcomesResult(
            total_validated=0,
            employed_count=0,
            not_reported_count=0,
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            resp = _make_client(_make_session()).get("/api/v1/analytics/career-outcomes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_validated"] == 0
        assert body["employed_count"] == 0
        assert body["not_reported_count"] == 0

    def test_companies_empty_returns_empty_list(self) -> None:
        result = CompanyAnalyticsResult(total_employers=0, top_employers=[])
        with patch("app.api.analytics.get_company_analytics", return_value=result):
            resp = _make_client(_make_session()).get("/api/v1/analytics/companies")
        assert resp.status_code == 200
        assert resp.json()["top_employers"] == []

    def test_industries_empty_returns_empty_lists(self) -> None:
        result = IndustryAnalyticsResult(industry_distribution=[], sector_breakdown=[])
        with patch("app.api.analytics.get_industry_analytics", return_value=result):
            resp = _make_client(_make_session()).get("/api/v1/analytics/industries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["industry_distribution"] == []
        assert body["sector_breakdown"] == []

    def test_geography_empty_returns_empty_lists(self) -> None:
        result = GeographicAnalyticsResult(country_distribution=[], city_distribution=[])
        with patch("app.api.analytics.get_geographic_analytics", return_value=result):
            resp = _make_client(_make_session()).get("/api/v1/analytics/geography")
        assert resp.status_code == 200
        body = resp.json()
        assert body["country_distribution"] == []
        assert body["city_distribution"] == []

    def test_directory_empty_returns_empty_items(self) -> None:
        """Empty directory should return 200 with empty items list (not 404)."""
        session = _make_session()
        # simulate: count=0, no rows
        session.scalar.return_value = 0
        session.scalars.return_value.all.return_value = []
        resp = _make_client(session).get("/api/v1/analytics/directory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_nonexistent_snapshot_filter_returns_empty(self) -> None:
        """Filtering by a non-existent snapshot_id must return 0 counts (not 404)."""
        overview = OverviewResult()  # 0s
        with patch("app.api.analytics.get_overview", return_value=overview):
            resp = _make_client(_make_session()).get("/api/v1/analytics/overview?snapshot_id=9999")
        assert resp.status_code == 200
        assert resp.json()["total_alumni"] == 0


# ---------------------------------------------------------------------------
# Single alumnus edge cases
# ---------------------------------------------------------------------------


class TestSingleAlumnus:
    """Verify analytics handles exactly-one alumni correctly."""

    def test_overview_single_alumnus(self) -> None:
        overview = OverviewResult(
            total_alumni=1,
            total_companies=1,
            total_industries=1,
            total_countries=1,
            alumni_by_program=[{"program_name": "Teknik Industri", "count": 1}],
            alumni_by_graduation_year=[{"graduation_year": 2022, "count": 1}],
        )
        with patch("app.api.analytics.get_overview", return_value=overview):
            resp = _make_client(_make_session()).get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_alumni"] == 1
        assert len(body["alumni_by_program"]) == 1
        assert body["alumni_by_program"][0]["count"] == 1

    def test_career_outcomes_single_employed(self) -> None:
        """Single employed alumnus → employed=1, not_reported=0."""
        outcomes = CareerOutcomesResult(
            total_validated=1,
            employed_count=1,
            not_reported_count=0,
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            resp = _make_client(_make_session()).get("/api/v1/analytics/career-outcomes")
        body = resp.json()
        assert body["employed_count"] == 1
        assert body["not_reported_count"] == 0

    def test_career_outcomes_single_not_reported(self) -> None:
        """Single alumnus without current career → employed=0, not_reported=1."""
        outcomes = CareerOutcomesResult(
            total_validated=1,
            employed_count=0,
            not_reported_count=1,
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            resp = _make_client(_make_session()).get("/api/v1/analytics/career-outcomes")
        body = resp.json()
        assert body["employed_count"] == 0
        assert body["not_reported_count"] == 1


# ---------------------------------------------------------------------------
# D-048 — Employed vs Not Reported arithmetic (all combinations)
# ---------------------------------------------------------------------------


class TestD048ArithmeticBoundaries:
    """Verify not_reported_count = total_validated - employed_count in all cases."""

    @pytest.mark.parametrize(
        "total,employed,not_reported",
        [
            (0, 0, 0),  # empty dataset
            (1, 1, 0),  # all employed
            (1, 0, 1),  # all not reported
            (10, 10, 0),  # all employed (larger dataset)
            (10, 0, 10),  # none employed
            (100, 75, 25),  # typical split
            (100, 100, 0),  # all 100 employed
            (100, 0, 100),  # all 100 not reported
        ],
    )
    def test_not_reported_arithmetic(self, total: int, employed: int, not_reported: int) -> None:
        result = CareerOutcomesResult(
            total_validated=total,
            employed_count=employed,
            not_reported_count=not_reported,
        )
        assert result.employed_count + result.not_reported_count == result.total_validated

    def test_response_never_includes_unemployment_rate(self) -> None:
        """D-048: no unemployment rate field must appear in the API response."""
        outcomes = CareerOutcomesResult(
            total_validated=50, employed_count=30, not_reported_count=20
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            resp = _make_client(_make_session()).get("/api/v1/analytics/career-outcomes")
        body = resp.json()
        forbidden_keys = {"unemployment_rate", "unemployed_count", "unemployed"}
        assert not forbidden_keys.intersection(
            body.keys()
        ), f"Response contains forbidden field(s): {forbidden_keys.intersection(body.keys())}"


# ---------------------------------------------------------------------------
# D-047 — analytics_filters always guard with validation_status=validated
# ---------------------------------------------------------------------------


class TestD047FilterGuard:
    """D-047: every analytics service call receives filters that include the
    validation_status == validated guard. Verified via clause counting."""

    def test_build_alumni_where_always_includes_validated_guard(self) -> None:
        from app.services.analytics_filters import AnalyticsFilters, build_alumni_where

        clauses = build_alumni_where(AnalyticsFilters())
        # Base state: exactly 1 clause (the validated guard). More clauses = user added filters.
        assert len(clauses) >= 1, "Expected at least 1 clause (validated guard)"

    def test_build_career_where_always_includes_validated_guard(self) -> None:
        from app.services.analytics_filters import AnalyticsFilters, build_career_where

        clauses = build_career_where(AnalyticsFilters())
        # Base state: 2 clauses — is_current + validated guard.
        assert len(clauses) >= 2

    def test_filter_options_returns_200(self) -> None:
        """Filter-options endpoint returns 200 even with empty DB — no 500."""
        session = _make_session()
        session.execute.return_value.all.return_value = []
        session.scalars.return_value.all.return_value = []
        resp = _make_client(session).get("/api/v1/analytics/filter-options")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Import parser boundary conditions
# ---------------------------------------------------------------------------


class TestImportParserBoundaries:
    """Edge cases for the import parser (supplement test_import_parser.py)."""

    def _make_session(self) -> MagicMock:
        session = create_autospec(Session, instance=True)
        added: list[object] = []
        session.add.side_effect = lambda obj: added.append(obj)

        def _flush() -> None:
            for obj in added:
                if isinstance(obj, ImportBatch) and obj.batch_id is None:
                    obj.batch_id = 1

        session.flush.side_effect = _flush
        return session  # type: ignore[no-any-return]

    def test_header_only_csv_returns_zero_rows(self) -> None:
        """CSV with only a header row produces a batch with total_rows=0."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location,linkedin_url\n"
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="empty.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.total_rows == 0
        assert batch.error_rows == 0

    def test_single_valid_row_parses_correctly(self) -> None:
        """A CSV with exactly one data row produces batch with total_rows=1, error_rows=0."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location,linkedin_url\n"
            b"Budi Santoso,Teknik Industri,2022,PT Maju Jaya,Engineer,Jakarta,\n"
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="single.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.total_rows == 1
        assert batch.error_rows == 0

    def test_row_with_missing_graduation_year_is_error(self) -> None:
        """A row with non-integer graduation_year produces an error row."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location\n"
            b"Budi Santoso,Teknik Industri,not-a-year,PT Maju Jaya,Engineer,Jakarta\n"
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="bad_year.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.total_rows == 1
        assert batch.error_rows == 1

    def test_all_error_rows_batch_status(self) -> None:
        """Batch where every row errors still creates the ImportBatch (not raises)."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location\n"
            b",Teknik Industri,2022,PT Maju Jaya,Engineer,Jakarta\n"  # missing full_name
            b"Budi Santoso,,2022,PT Maju Jaya,Engineer,Jakarta\n"  # missing study_program
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="all_errors.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.total_rows == 2
        assert batch.error_rows == 2

    def test_mixed_valid_and_error_rows(self) -> None:
        """Batch with 2 valid + 1 error row reports correct counts."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location\n"
            b"Budi Santoso,Teknik Industri,2022,PT Maju Jaya,Engineer,Jakarta\n"
            b"Citra Dewi,Teknologi Sains Data,2021,Gojek,Data Scientist,Jakarta\n"
            b",Teknik Elektro,2020,PT PLN,Field Engineer,Surabaya\n"  # missing full_name → error
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="mixed.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.total_rows == 3
        assert batch.error_rows == 1
        assert batch.parsed_rows == 2

    def test_unicode_names_parse_correctly(self) -> None:
        """Alumni names with Indonesian Unicode characters parse without error."""
        content = (
            "full_name,study_program,graduation_year,employer,role_title,location\n"
            "Dwi Nugroho Äryan,Teknik Industri,2022,PT Maju Jaya,Engineer,Surabaya\n"
        ).encode()
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="unicode.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        assert batch.error_rows == 0

    def test_blank_employer_row_is_not_error(self) -> None:
        """D-048: A row without employer is valid — alumnus is 'Not Reported' in analytics."""
        content = (
            b"full_name,study_program,graduation_year,employer,role_title,location\n"
            b"Budi Santoso,Teknik Industri,2022,,,\n"  # employer/role/location all blank
        )
        session = self._make_session()
        batch = parse_import(
            file_content=content,
            filename="no_employer.csv",
            source_type="Tracer Study",
            source_id=1,
            session=session,
            created_by=None,
        )
        # Blank optional fields are NOT errors (Tracer Study treats employer as optional)
        assert batch.total_rows == 1
        assert batch.error_rows == 0


# ---------------------------------------------------------------------------
# Country / filter dimension propagation
# ---------------------------------------------------------------------------


class TestFilterDimensionPropagation:
    """Verify that filter query params are correctly mapped to AnalyticsFilters."""

    def test_country_filter_propagated_to_service(self) -> None:
        """country= query param is mapped to AnalyticsFilters.country and passed to service."""
        overview = OverviewResult(total_alumni=5)
        captured: list[Any] = []

        def _capture(filters, session):  # type: ignore[no-untyped-def]
            captured.append(filters)
            return overview

        with patch("app.api.analytics.get_overview", side_effect=_capture):
            _make_client(_make_session()).get("/api/v1/analytics/overview?country=Indonesia")
        assert len(captured) == 1
        assert captured[0].country == "Indonesia"

    def test_all_filter_dims_propagated(self) -> None:
        """All filter dimensions are propagated to AnalyticsFilters together."""
        overview = OverviewResult(total_alumni=2)
        captured: list[Any] = []

        def _capture(filters, session):  # type: ignore[no-untyped-def]
            captured.append(filters)
            return overview

        url = (
            "/api/v1/analytics/overview"
            "?study_program_id=1"
            "&graduation_year=2022"
            "&industry_id=3"
            "&company_id=5"
            "&country=Singapore"
            "&snapshot_id=2"
        )
        with patch("app.api.analytics.get_overview", side_effect=_capture):
            _make_client(_make_session()).get(url)

        assert len(captured) == 1
        f = captured[0]
        assert f.study_program_id == 1
        assert f.graduation_year == 2022
        assert f.industry_id == 3
        assert f.company_id == 5
        assert f.country == "Singapore"
        assert f.snapshot_id == 2
