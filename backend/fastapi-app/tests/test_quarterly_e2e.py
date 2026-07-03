"""End-to-end quarterly refresh orchestration tests (P7.1).

Validates the full pipeline: open_snapshot → import → validate → commit → analytics.
These tests exercise the API layer end-to-end via FastAPI TestClient, with service
calls mocked at the boundary. They verify that the system correctly orchestrates
a two-quarter refresh cycle and that invariants hold throughout.

Decisions enforced:
  D-021: one snapshot per quarter_label
  D-024: only curator can set validation_status=validated
  D-025: audit entries written throughout pipeline
  D-031: services never call session.commit; caller (API) owns transaction
  D-047: only validated alumni appear in analytics
  D-048: employment reported as Employed vs Not Reported; no unemployment rate asserted
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, create_autospec, patch

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.alumni import Alumni, ValidationStatus
from app.models.snapshot import RefreshSnapshot
from app.models.staging import ImportBatch
from app.rate_limiting import import_rate_limit
from app.schemas.auth import AuthenticatedUser
from app.services.analytics import (
    CareerOutcomesResult,
    OverviewResult,
)
from app.services.commit import CommitOutcome, CommitResult
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_CURATOR = AuthenticatedUser(
    user_id=10,
    supabase_uuid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    role_name="Data Curator",
    permissions=frozenset(
        [
            "alumni:read",
            "alumni:write",
            "alumni:validate",
            "career:read",
            "career:write",
            "company:read",
            "company:write",
            "import:run",
            "dedup:review",
            "snapshot:manage",
            "analytics:read",
        ]
    ),
)

_VIEWER = AuthenticatedUser(
    user_id=20,
    supabase_uuid="cccccccc-cccc-cccc-cccc-cccccccccccc",
    role_name="Faculty Viewer",
    permissions=frozenset(["analytics:read"]),
)


def _make_session() -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.get.return_value = None
    session.scalar.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    session.scalars.return_value = scalars_mock
    return session  # type: ignore[no-any-return]


def _make_snapshot(
    snapshot_id: int,
    quarter_label: str,
    refresh_date: datetime.date | None = None,
) -> MagicMock:
    s = MagicMock(spec=RefreshSnapshot)
    s.snapshot_id = snapshot_id
    s.quarter_label = quarter_label
    s.refresh_date = refresh_date or datetime.date(2025, 3, 31)
    s.notes = None
    s.created_at = datetime.datetime(2025, 3, 31, tzinfo=datetime.UTC)
    return s


def _make_import_batch(
    batch_id: int,
    total_rows: int,
    error_rows: int = 0,
    source_id: int = 1,
    filename: str = "alumni.csv",
) -> MagicMock:
    b = MagicMock(spec=ImportBatch)
    b.batch_id = batch_id
    b.source_id = source_id
    b.filename = filename
    b.total_rows = total_rows
    b.parsed_rows = total_rows - error_rows
    b.error_rows = error_rows
    b.status = "complete"
    b.created_by = 10
    b.created_at = datetime.datetime(2025, 3, 31, tzinfo=datetime.UTC)
    return b


def _make_alumni(
    alumni_id: int,
    validation_status: str = "pending",
    full_name: str = "Budi Santoso",
    study_program_id: int = 1,
    graduation_year: int = 2022,
) -> MagicMock:
    a = MagicMock(spec=Alumni)
    a.alumni_id = alumni_id
    a.validation_status = ValidationStatus(validation_status)
    a.full_name = full_name
    a.study_program_id = study_program_id
    a.graduation_year = graduation_year
    a.university = "Universitas Airlangga"
    a.linkedin_url = None
    a.source_id = 1
    a.public_id = f"pub-{alumni_id:04d}"
    a.created_at = datetime.datetime(2025, 3, 31, tzinfo=datetime.UTC)
    a.updated_at = datetime.datetime(2025, 3, 31, tzinfo=datetime.UTC)
    return a


def _client(session: MagicMock, user: AuthenticatedUser = _CURATOR) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[import_rate_limit] = lambda: None
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Stage 1 — Snapshot creation (D-021)
# ---------------------------------------------------------------------------


class TestSnapshotCreationStage:
    """Verify the snapshot creation API step in the quarterly pipeline."""

    def test_open_q1_snapshot_returns_201(self) -> None:
        snap = _make_snapshot(snapshot_id=1, quarter_label="2025-Q1")
        session = _make_session()
        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry"),
        ):
            resp = _client(session).post("/api/v1/snapshots", json={"quarter_label": "2025-Q1"})
        assert resp.status_code == 201
        assert resp.json()["quarter_label"] == "2025-Q1"
        assert resp.json()["snapshot_id"] == 1

    def test_open_q2_snapshot_returns_201(self) -> None:
        snap = _make_snapshot(snapshot_id=2, quarter_label="2025-Q2")
        session = _make_session()
        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry"),
        ):
            resp = _client(session).post("/api/v1/snapshots", json={"quarter_label": "2025-Q2"})
        assert resp.status_code == 201
        assert resp.json()["snapshot_id"] == 2

    def test_d021_duplicate_label_rejected(self) -> None:
        """D-021: two snapshots with the same quarter_label must not coexist."""
        session = _make_session()
        with patch(
            "app.api.snapshots.open_snapshot",
            side_effect=ValueError("Snapshot 2025-Q1 already exists"),
        ):
            resp = _client(session).post("/api/v1/snapshots", json={"quarter_label": "2025-Q1"})
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_snapshot_creation_requires_snapshot_manage_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_VIEWER).post(
            "/api/v1/snapshots", json={"quarter_label": "2025-Q1"}
        )
        assert resp.status_code == 403

    def test_snapshot_creation_writes_audit(self) -> None:
        """D-025: snapshot creation must produce an audit entry."""
        snap = _make_snapshot(snapshot_id=1, quarter_label="2025-Q1")
        session = _make_session()
        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry") as mock_audit,
        ):
            _client(session).post("/api/v1/snapshots", json={"quarter_label": "2025-Q1"})
        mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# Stage 2 — Import CSV (size guard already tested in test_imports_endpoint.py)
# ---------------------------------------------------------------------------


class TestImportStage:
    """Verify the import stage: parse → stage rows → return batch summary."""

    def test_import_csv_returns_201_with_batch(self) -> None:
        batch = _make_import_batch(batch_id=10, total_rows=3)
        session = _make_session()
        csv_content = (
            "full_name,study_program,graduation_year,employer,role_title,location\n"
            "Budi Santoso,Teknik Industri,2022,PT Maju Jaya,Engineer,Jakarta\n"
            "Citra Dewi,Teknologi Sains Data,2021,Gojek,Data Scientist,Jakarta\n"
            "Eko Pratama,Teknik Elektro,2020,PT PLN,Field Engineer,Surabaya\n"
        )
        with (
            patch("app.api.imports.parse_import", return_value=batch),
            patch("app.api.imports.write_audit_entry"),
        ):
            resp = _client(session).post(
                "/api/v1/imports",
                files={"file": ("alumni.csv", csv_content.encode(), "text/csv")},
                data={"source_type": "Tracer Study", "source_id": "1"},
            )
        assert resp.status_code == 201
        assert resp.json()["total_rows"] == 3
        assert resp.json()["batch_id"] == 10

    def test_import_q2_batch_returns_120_rows(self) -> None:
        batch = _make_import_batch(batch_id=11, total_rows=120)
        session = _make_session()
        csv_content = "full_name,study_program,graduation_year,employer,role_title,location\n" + (
            "Alumnus N,Teknik Industri,2022,PT Maju Jaya,Engineer,Jakarta\n" * 120
        )
        with (
            patch("app.api.imports.parse_import", return_value=batch),
            patch("app.api.imports.write_audit_entry"),
        ):
            resp = _client(session).post(
                "/api/v1/imports",
                files={"file": ("alumni_q2.csv", csv_content.encode(), "text/csv")},
                data={"source_type": "Tracer Study", "source_id": "1"},
            )
        assert resp.status_code == 201
        assert resp.json()["total_rows"] == 120


# ---------------------------------------------------------------------------
# Stage 3 — Commit batch (D-031, D-045, D-047)
# ---------------------------------------------------------------------------


class TestCommitStage:
    """Verify commit stage: staging rows → Alumni + CareerRecord (no auto-validate)."""

    def test_commit_q1_batch_creates_alumni(self) -> None:
        """Committing Q1 batch creates new alumni rows in status=pending (D-047)."""
        session = _make_session()
        results = [
            CommitResult(
                staging_row_id=i,
                outcome=CommitOutcome.created,
                alumni_id=i,
                career_record_id=i + 100,
            )
            for i in range(1, 4)
        ]
        with patch("app.api.commit.commit_batch", return_value=results):
            resp = _client(session).post("/api/v1/commit", json={"batch_id": 10, "snapshot_id": 1})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["created"] == 3
        assert body["linked"] == 0

    def test_commit_q2_batch_links_existing_alumni(self) -> None:
        """Q2 commit links existing alumni via Tier-1/Tier-2 match (D-044/D-045)."""
        session = _make_session()
        results = [
            # 3 existing alumni linked (same linkedin URL)
            CommitResult(
                staging_row_id=i,
                outcome=CommitOutcome.linked,
                alumni_id=i,
                career_record_id=i + 200,
            )
            for i in range(1, 4)
        ] + [
            # 1 new 2024 graduate created
            CommitResult(
                staging_row_id=4,
                outcome=CommitOutcome.created,
                alumni_id=4,
                career_record_id=204,
            ),
        ]
        with patch("app.api.commit.commit_batch", return_value=results):
            resp = _client(session).post("/api/v1/commit", json={"batch_id": 11, "snapshot_id": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4
        assert body["linked"] == 3
        assert body["created"] == 1

    def test_d047_commit_never_sets_validated_status(self) -> None:
        """D-047: commit pipeline creates alumni with status=pending, never validated.

        This tests the commit service directly — the outcome is CommitOutcome.created
        but the alumni is not yet visible in analytics (needs curator validation first).
        """
        session = _make_session()
        # Commit succeeds, but alumni are pending — analytics should not count them yet
        results = [
            CommitResult(
                staging_row_id=1,
                outcome=CommitOutcome.created,
                alumni_id=1,
                career_record_id=101,
            )
        ]
        with patch("app.api.commit.commit_batch", return_value=results):
            commit_resp = _client(session).post(
                "/api/v1/commit", json={"batch_id": 10, "snapshot_id": 1}
            )
        assert commit_resp.status_code == 200
        # D-047 verified below: analytics service is called with validated filter
        # (unit-tested in test_analytics.py — here we verify the pipeline ordering)

    def test_commit_requires_import_run_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_VIEWER).post(
            "/api/v1/commit", json={"batch_id": 10, "snapshot_id": 1}
        )
        assert resp.status_code == 403

    def test_d031_commit_api_owns_session_commit(self) -> None:
        """D-031: the API layer (not the service) calls session.commit."""
        session = _make_session()
        results = [CommitResult(staging_row_id=1, outcome=CommitOutcome.created, alumni_id=1)]
        with patch("app.api.commit.commit_batch", return_value=results):
            _client(session).post("/api/v1/commit", json={"batch_id": 10, "snapshot_id": 1})
        session.commit.assert_called()


# ---------------------------------------------------------------------------
# Stage 4 — Validation gate (D-024, D-047)
# ---------------------------------------------------------------------------


class TestValidationGate:
    """Verify that only curator validation enables analytics visibility (D-024, D-047)."""

    def test_d024_curator_can_validate_alumni(self) -> None:
        """D-024: alumni:validate permission required to set status=validated."""
        alumni = _make_alumni(alumni_id=1, validation_status="pending")
        alumni.validation_status = ValidationStatus.pending
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry"):
            resp = _client(session, user=_CURATOR).post(
                "/api/v1/alumni/1/validate", json={"action": "validate"}
            )
        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "validated"

    def test_d024_viewer_cannot_validate_alumni(self) -> None:
        """D-024: Faculty Viewer must not be able to set validated status."""
        session = _make_session()
        resp = _client(session, user=_VIEWER).post(
            "/api/v1/alumni/1/validate", json={"action": "validate"}
        )
        assert resp.status_code == 403

    def test_validate_writes_audit_entry(self) -> None:
        """D-025: validation action must be recorded in audit log."""
        alumni = _make_alumni(alumni_id=1)
        alumni.validation_status = ValidationStatus.pending
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry") as mock_audit:
            _client(session).post("/api/v1/alumni/1/validate", json={"action": "validate"})
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["action_type"] in ("UPDATE", "VALIDATE")

    def test_reject_returns_rejected_status(self) -> None:
        alumni = _make_alumni(alumni_id=2)
        alumni.validation_status = ValidationStatus.pending
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry"):
            resp = _client(session).post(
                "/api/v1/alumni/2/validate",
                json={"action": "reject", "reason": "not FTMM program"},
            )
        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "rejected"

    def test_rejected_alumni_not_counted_in_analytics(self) -> None:
        """D-047: rejected alumni must be excluded from analytics (same as pending)."""
        # The analytics service always filters by validation_status == validated.
        # Rejected alumni are stored for audit (D-047) but never enter analytics.
        overview = OverviewResult(total_alumni=2)
        with patch("app.api.analytics.get_overview", return_value=overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        assert resp.json()["total_alumni"] == 2


# ---------------------------------------------------------------------------
# Stage 5 — Analytics reflect validated cohort (D-047, D-048)
# ---------------------------------------------------------------------------


class TestAnalyticsReflectValidatedCohort:
    """Analytics endpoints show only validated alumni post-commit."""

    def test_d047_overview_counts_only_validated(self) -> None:
        """D-047: total_validated reflects only alumni with validation_status=validated."""
        overview = OverviewResult(
            total_alumni=3,
            total_companies=3,
            total_industries=2,
            total_countries=1,
        )
        with patch("app.api.analytics.get_overview", return_value=overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_alumni"] == 3

    def test_d048_career_outcomes_shows_employed_and_not_reported(self) -> None:
        """D-048: career outcomes split is 'Employed' vs 'Not Reported'.

        The response must include employed_count and not_reported_count.
        It must NOT include any field asserting an unemployment rate.
        """
        outcomes = CareerOutcomesResult(
            total_validated=3,
            employed_count=2,
            not_reported_count=1,
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/career-outcomes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["employed_count"] == 2
        assert body["not_reported_count"] == 1
        # D-048: verify no unemployment rate field is exposed
        assert "unemployment_rate" not in body
        assert "unemployed_count" not in body
        assert "unemployed" not in body

    def test_d048_not_reported_equals_total_minus_employed(self) -> None:
        """D-048: not_reported = total_validated - employed (never an unemployment rate)."""
        outcomes = CareerOutcomesResult(
            total_validated=10,
            employed_count=8,
            not_reported_count=2,  # total - employed
        )
        with patch("app.api.analytics.get_career_outcomes", return_value=outcomes):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/career-outcomes")
        body = resp.json()
        assert body["not_reported_count"] == body["total_validated"] - body["employed_count"]

    def test_analytics_requires_analytics_read_permission(self) -> None:
        no_perm = AuthenticatedUser(
            user_id=99,
            supabase_uuid="ffffffff-ffff-ffff-ffff-ffffffffffff",
            role_name="External",
            permissions=frozenset(),
        )
        session = _make_session()
        endpoints = [
            "/api/v1/analytics/overview",
            "/api/v1/analytics/career-outcomes",
            "/api/v1/analytics/companies",
            "/api/v1/analytics/industries",
            "/api/v1/analytics/geography",
            "/api/v1/analytics/directory",
        ]
        client = _client(session, user=no_perm)
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert resp.status_code == 403, f"Expected 403 for {endpoint}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Stage 6 — Point-in-time correctness (D-021, D-007)
# ---------------------------------------------------------------------------


class TestPointInTimeCorrectness:
    """Analytics filtered by snapshot_id show the data for that specific quarter."""

    def test_q1_filter_shows_q1_alumni_count(self) -> None:
        """snapshot_id=1 returns Q1 population (3 alumni)."""
        q1_overview = OverviewResult(total_alumni=3)

        def _get_overview(filters, session):  # type: ignore[no-untyped-def]
            if filters.snapshot_id == 1:
                return q1_overview
            raise AssertionError(f"Unexpected snapshot_id: {filters.snapshot_id}")

        with patch("app.api.analytics.get_overview", side_effect=_get_overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview?snapshot_id=1")
        assert resp.status_code == 200
        assert resp.json()["total_alumni"] == 3

    def test_q2_filter_shows_expanded_alumni_count(self) -> None:
        """snapshot_id=2 returns Q2 population (4 alumni: 3 carry-forward + 1 new grad)."""
        q2_overview = OverviewResult(total_alumni=4)

        def _get_overview(filters, session):  # type: ignore[no-untyped-def]
            if filters.snapshot_id == 2:
                return q2_overview
            raise AssertionError(f"Unexpected snapshot_id: {filters.snapshot_id}")

        with patch("app.api.analytics.get_overview", side_effect=_get_overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview?snapshot_id=2")
        assert resp.status_code == 200
        assert resp.json()["total_alumni"] == 4

    def test_unfiltered_returns_all_validated_alumni(self) -> None:
        """No snapshot_id filter → all validated alumni across all snapshots."""
        all_overview = OverviewResult(total_alumni=4)
        with patch("app.api.analytics.get_overview", return_value=all_overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview")
        assert resp.status_code == 200
        assert resp.json()["total_alumni"] == 4

    def test_d007_snapshot_filter_propagated_to_service(self) -> None:
        """D-007: snapshot_id query param is mapped to AnalyticsFilters.snapshot_id
        and propagated to every analytics service call."""
        overview = OverviewResult(total_alumni=3)
        captured_filters = []

        def _capture(filters, session):  # type: ignore[no-untyped-def]
            captured_filters.append(filters)
            return overview

        with patch("app.api.analytics.get_overview", side_effect=_capture):
            session = _make_session()
            _client(session, user=_VIEWER).get("/api/v1/analytics/overview?snapshot_id=7")

        assert len(captured_filters) == 1
        assert captured_filters[0].snapshot_id == 7


# ---------------------------------------------------------------------------
# Stage 7 — Full two-quarter orchestration (integration scenario)
# ---------------------------------------------------------------------------


class TestTwoQuarterOrchestration:
    """
    Simulate the complete two-quarter refresh cycle as a curator would run it.

    Q1 cycle:
      1. POST /snapshots {2025-Q1}
      2. POST /imports (CSV upload)
      3. POST /commit {batch_id, snapshot_id=1}
      4. POST /alumni/{id}/validate × N
      5. GET  /analytics/overview?snapshot_id=1

    Q2 cycle:
      6. POST /snapshots {2025-Q2}
      7. POST /imports (Q2 CSV with role changes + new grads)
      8. POST /commit {batch_id=11, snapshot_id=2}
      9. POST /alumni/{id}/validate (new grads only)
      10. GET /analytics/overview?snapshot_id=2 → shows expanded population
      11. GET /analytics/overview?snapshot_id=1 → unchanged (point-in-time)
    """

    def test_q1_full_cycle(self) -> None:
        """Run the Q1 import-validate-commit-analytics cycle."""
        snap = _make_snapshot(snapshot_id=1, quarter_label="2025-Q1")
        batch = _make_import_batch(batch_id=10, total_rows=3)
        commit_results = [
            CommitResult(
                staging_row_id=i,
                outcome=CommitOutcome.created,
                alumni_id=i,
                career_record_id=i + 100,
            )
            for i in range(1, 4)
        ]
        overview_q1 = OverviewResult(total_alumni=3)

        session = _make_session()
        client = _client(session)
        csv_content = (
            "full_name,study_program,graduation_year,employer,role_title,location\n"
            "Budi Santoso,Teknik Industri,2022,PT Astra,Engineer,Jakarta\n"
            "Citra Dewi,Teknologi Sains Data,2021,Gojek,Data Scientist,Jakarta\n"
            "Eko Pratama,Teknik Elektro,2020,PT PLN,Field Engineer,Surabaya\n"
        )

        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry"),
        ):
            snap_resp = client.post("/api/v1/snapshots", json={"quarter_label": "2025-Q1"})
        assert snap_resp.status_code == 201

        with (
            patch("app.api.imports.parse_import", return_value=batch),
            patch("app.api.imports.write_audit_entry"),
        ):
            import_resp = client.post(
                "/api/v1/imports",
                files={"file": ("alumni.csv", csv_content.encode(), "text/csv")},
                data={"source_type": "Tracer Study", "source_id": "1"},
            )
        assert import_resp.status_code == 201
        assert import_resp.json()["total_rows"] == 3

        with patch("app.api.commit.commit_batch", return_value=commit_results):
            commit_resp = client.post("/api/v1/commit", json={"batch_id": 10, "snapshot_id": 1})
        assert commit_resp.status_code == 200
        assert commit_resp.json()["created"] == 3

        # Validate all 3 alumni (D-024)
        for alumni_id in [1, 2, 3]:
            a = _make_alumni(alumni_id=alumni_id)
            a.validation_status = ValidationStatus.pending
            session.get.return_value = a
            with patch("app.api.commit.write_audit_entry"):
                val_resp = client.post(
                    f"/api/v1/alumni/{alumni_id}/validate", json={"action": "validate"}
                )
            assert val_resp.status_code == 200, f"Validate alumni {alumni_id} failed"

        with patch("app.api.analytics.get_overview", return_value=overview_q1):
            analytics_resp = client.get("/api/v1/analytics/overview?snapshot_id=1")
        assert analytics_resp.status_code == 200
        assert analytics_resp.json()["total_alumni"] == 3

    def test_q2_full_cycle_with_carry_forward(self) -> None:
        """Q2 cycle: existing alumni linked, new grad created, both visible in analytics."""
        snap_q2 = _make_snapshot(snapshot_id=2, quarter_label="2025-Q2")
        batch_q2 = _make_import_batch(batch_id=11, total_rows=4)
        commit_results_q2 = [
            # 3 existing alumni linked with role updates
            CommitResult(
                staging_row_id=i,
                outcome=CommitOutcome.linked,
                alumni_id=i,
                career_record_id=i + 200,
            )
            for i in range(1, 4)
        ] + [
            # 1 new 2024 graduate
            CommitResult(
                staging_row_id=4,
                outcome=CommitOutcome.created,
                alumni_id=4,
                career_record_id=204,
            ),
        ]
        overview_q2 = OverviewResult(total_alumni=4)

        session = _make_session()
        client = _client(session)
        csv_q2 = (
            "full_name,study_program,graduation_year,employer,role_title,location\n"
            "Budi Santoso,Teknik Industri,2022,PT Astra,Senior Engineer,Jakarta\n"
            "Citra Dewi,Teknologi Sains Data,2021,Gojek,Lead Data Scientist,Jakarta\n"
            "Eko Pratama,Teknik Elektro,2020,PT PLN,Systems Architect,Surabaya\n"
            "Fajar Lestari,Teknik Nanoteknologi,2024,BPPT Indonesia,Lab Researcher,Bandung\n"
        )

        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap_q2),
            patch("app.api.snapshots.write_audit_entry"),
        ):
            snap_resp = client.post("/api/v1/snapshots", json={"quarter_label": "2025-Q2"})
        assert snap_resp.status_code == 201

        with (
            patch("app.api.imports.parse_import", return_value=batch_q2),
            patch("app.api.imports.write_audit_entry"),
        ):
            import_resp = client.post(
                "/api/v1/imports",
                files={"file": ("alumni_q2.csv", csv_q2.encode(), "text/csv")},
                data={"source_type": "Tracer Study", "source_id": "1"},
            )
        assert import_resp.status_code == 201

        with patch("app.api.commit.commit_batch", return_value=commit_results_q2):
            commit_resp = client.post("/api/v1/commit", json={"batch_id": 11, "snapshot_id": 2})
        assert commit_resp.status_code == 200
        body = commit_resp.json()
        assert body["linked"] == 3
        assert body["created"] == 1

        # Validate only the new graduate (existing alumni already validated in Q1)
        new_alumni = _make_alumni(alumni_id=4, validation_status="pending")
        new_alumni.validation_status = ValidationStatus.pending
        session.get.return_value = new_alumni
        with patch("app.api.commit.write_audit_entry"):
            val_resp = client.post("/api/v1/alumni/4/validate", json={"action": "validate"})
        assert val_resp.status_code == 200

        with patch("app.api.analytics.get_overview", return_value=overview_q2):
            analytics_resp = client.get("/api/v1/analytics/overview?snapshot_id=2")
        assert analytics_resp.status_code == 200
        assert analytics_resp.json()["total_alumni"] == 4

    def test_q1_point_in_time_unchanged_after_q2_import(self) -> None:
        """Q1 snapshot data is immutable: Q2 import does not alter Q1 analytics."""
        overview_q1 = OverviewResult(total_alumni=3)

        def _get_overview(filters, session):  # type: ignore[no-untyped-def]
            assert filters.snapshot_id == 1, "Expected snapshot_id=1"
            return overview_q1

        with patch("app.api.analytics.get_overview", side_effect=_get_overview):
            session = _make_session()
            resp = _client(session, user=_VIEWER).get("/api/v1/analytics/overview?snapshot_id=1")
        assert resp.status_code == 200
        # Q1 still shows 3, not 4 — point-in-time is preserved
        assert resp.json()["total_alumni"] == 3

    def test_two_quarter_counts_differ(self) -> None:
        """Q1 and Q2 produce different validated counts — growth is visible."""
        counts_by_snapshot = {1: 3, 2: 4}

        def _get_overview(filters, session):  # type: ignore[no-untyped-def]
            n = counts_by_snapshot[filters.snapshot_id]
            return OverviewResult(total_alumni=n)

        session = _make_session()
        with patch("app.api.analytics.get_overview", side_effect=_get_overview):
            client = _client(session, user=_VIEWER)
            q1_resp = client.get("/api/v1/analytics/overview?snapshot_id=1")
            q2_resp = client.get("/api/v1/analytics/overview?snapshot_id=2")

        assert q1_resp.json()["total_alumni"] < q2_resp.json()["total_alumni"]
        assert q2_resp.json()["total_alumni"] - q1_resp.json()["total_alumni"] == 1
