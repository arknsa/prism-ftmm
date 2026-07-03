"""Tests for commit.py service + commit/validation API endpoints (P4.5).

Covers:
- commit_staging_row: created/linked (Tier-1)/pending_dedup/skipped_error/skipped_no_employer
- commit_batch: iterates rows, delegates to commit_staging_row
- D-020: _clear_current_career clears existing is_current before new CareerRecord
- D-024: alumni:validate endpoint is the only path to ValidationStatus.validated
- D-025: audit entries written for Alumni INSERT, CareerRecord INSERT, validate/reject
- D-031: service never commits; caller owns transaction
- D-045: Tier-2 match → pending_dedup until curator resolves
- D-047: pipeline never sets validation_status=validated; only curator can
- API: POST /commit, POST /alumni/{id}/validate, GET /alumni/{id}, GET /alumni
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.alumni import Alumni, ValidationStatus
from app.models.career import CareerRecord
from app.models.dedup import DedupCandidate
from app.models.staging import ImportBatch, StagingRow
from app.schemas.auth import AuthenticatedUser
from app.services.commit import (
    CommitOutcome,
    CommitResult,
    _clear_current_career,
    _normalize_linkedin_url_for_storage,
    commit_batch,
    commit_staging_row,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
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
            "import:run",
            "dedup:review",
            "snapshot:manage",
            "analytics:read",
        ]
    ),
)

_NO_PERM = AuthenticatedUser(
    user_id=99,
    supabase_uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    role_name="Faculty Viewer",
    permissions=frozenset(["analytics:read"]),
)


def _make_row(
    staging_row_id: int = 1,
    batch_id: int = 10,
    row_status: str = "pending",
    raw_full_name: str | None = "Budi Santoso",
    raw_study_program: str | None = "teknik industri",
    raw_graduation_year: int | None = 2022,
    raw_employer: str | None = "PT Maju Jaya",
    raw_role_title: str | None = "Software Engineer",
    raw_linkedin_url: str | None = None,
) -> MagicMock:
    row = MagicMock(spec=StagingRow)
    row.staging_row_id = staging_row_id
    row.batch_id = batch_id
    row.row_status = row_status
    row.raw_full_name = raw_full_name
    row.raw_study_program = raw_study_program
    row.raw_graduation_year = raw_graduation_year
    row.raw_employer = raw_employer
    row.raw_role_title = raw_role_title
    row.raw_linkedin_url = raw_linkedin_url
    return row


def _make_alumni(alumni_id: int = 1, validation_status: str = "pending") -> MagicMock:
    a = MagicMock(spec=Alumni)
    a.alumni_id = alumni_id
    a.validation_status = ValidationStatus(validation_status)
    a.full_name = "Budi Santoso"
    a.study_program_id = 2
    a.graduation_year = 2022
    a.university = "Universitas Airlangga"
    a.linkedin_url = None
    a.source_id = 1
    a.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    a.updated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    a.public_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    return a


def _make_career(career_record_id: int = 1, alumni_id: int = 1) -> MagicMock:
    c = MagicMock(spec=CareerRecord)
    c.career_record_id = career_record_id
    c.alumni_id = alumni_id
    c.company_id = 5
    c.role_title = "Software Engineer"
    c.seniority = "Mid"
    c.is_current = True
    c.snapshot_id = 3
    c.source_id = 1
    return c


def _make_program(program_id: int = 2, is_ftmm_valid: bool = True) -> MagicMock:
    p = MagicMock()
    p.program_id = program_id
    p.is_ftmm_valid = is_ftmm_valid
    p.program_name = "Industrial Engineering"
    return p


def _make_company(company_id: int = 5) -> MagicMock:
    c = MagicMock()
    c.company_id = company_id
    c.canonical_name = "PT Maju Jaya"
    return c


def _make_session() -> MagicMock:
    s = create_autospec(Session, instance=True)
    s.get.return_value = None
    s.scalar.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    s.scalars.return_value = scalars_mock
    return s


def _make_batch(batch_id: int = 10, source_id: int = 1) -> MagicMock:
    b = MagicMock(spec=ImportBatch)
    b.batch_id = batch_id
    b.source_id = source_id
    return b


# ---------------------------------------------------------------------------
# _normalize_linkedin_url_for_storage
# ---------------------------------------------------------------------------


class TestNormalizeLinkedinUrlForStorage:
    def test_none_returns_none(self) -> None:
        assert _normalize_linkedin_url_for_storage(None) is None

    def test_blank_returns_none(self) -> None:
        assert _normalize_linkedin_url_for_storage("   ") is None

    def test_strips_and_lowercases(self) -> None:
        result = _normalize_linkedin_url_for_storage("  HTTPS://LinkedIn.com/in/Budi  ")
        assert result == "https://linkedin.com/in/budi"

    def test_removes_trailing_slash(self) -> None:
        result = _normalize_linkedin_url_for_storage("https://linkedin.com/in/budi/")
        assert result == "https://linkedin.com/in/budi"


# ---------------------------------------------------------------------------
# _clear_current_career (D-020)
# ---------------------------------------------------------------------------


class TestClearCurrentCareer:
    def test_clears_existing_is_current(self) -> None:
        career = _make_career()
        career.is_current = True
        session = _make_session()
        session.scalar.return_value = career
        _clear_current_career(alumni_id=1, session=session)
        assert career.is_current is False

    def test_no_existing_is_current_noop(self) -> None:
        session = _make_session()
        session.scalar.return_value = None
        _clear_current_career(alumni_id=1, session=session)  # should not raise


# ---------------------------------------------------------------------------
# commit_staging_row
# ---------------------------------------------------------------------------

_PATCH_BASE = "app.services.commit"


class TestCommitStagingRowSkips:
    def test_skips_error_rows(self) -> None:
        row = _make_row(row_status="error")
        session = _make_session()
        result = commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)
        assert result.outcome == CommitOutcome.skipped_error
        assert result.alumni_id is None

    def test_error_rows_do_not_add(self) -> None:
        row = _make_row(row_status="error")
        session = _make_session()
        commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)
        session.add.assert_not_called()

    def test_does_not_commit(self) -> None:
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()
        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
        ):
            commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)
        session.commit.assert_not_called()


class TestCommitStagingRowCreate:
    def test_creates_new_alumni(self) -> None:
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 99

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            result = commit_staging_row(
                row, snapshot_id=3, source_id=1, actor_id=10, session=session
            )

        assert result.outcome == CommitOutcome.created
        alumni_objs = [o for o in added_items if isinstance(o, Alumni)]
        assert len(alumni_objs) == 1

    def test_creates_career_record(self) -> None:
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 99

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            result = commit_staging_row(
                row, snapshot_id=3, source_id=1, actor_id=10, session=session
            )

        career_objs = [o for o in added_items if isinstance(o, CareerRecord)]
        assert len(career_objs) == 1
        assert result.career_record_id is not None

    def test_snapshot_id_on_career(self) -> None:
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 99

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            commit_staging_row(row, snapshot_id=7, source_id=1, actor_id=10, session=session)

        career_objs = [o for o in added_items if isinstance(o, CareerRecord)]
        assert career_objs[0].snapshot_id == 7

    def test_alumni_initial_status_not_validated(self) -> None:
        """D-047: pipeline never sets validation_status=validated."""
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 99

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)

        alumni_objs = [o for o in added_items if isinstance(o, Alumni)]
        assert alumni_objs[0].validation_status != ValidationStatus.validated

    def test_audit_written_for_alumni_and_career(self) -> None:
        """D-025: two audit entries written (Alumni INSERT + CareerRecord INSERT)."""
        row = _make_row()
        program = _make_program()
        company = _make_company()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 99

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry") as mock_audit,
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)

        assert mock_audit.call_count == 2
        tables = {c.kwargs["table_name"] for c in mock_audit.call_args_list}
        assert "alumni" in tables
        assert "career_record" in tables

    def test_no_employer_skips_career_record(self) -> None:
        row = _make_row(raw_employer=None)
        program = _make_program()
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 42

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=None),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
        ):
            result = commit_staging_row(
                row, snapshot_id=1, source_id=1, actor_id=10, session=session
            )

        career_objs = [o for o in added_items if isinstance(o, CareerRecord)]
        assert len(career_objs) == 0
        assert result.career_record_id is None


class TestCommitStagingRowTier1:
    def test_tier1_match_links_existing_alumni(self) -> None:
        """Tier-1: exact linkedin_url → auto-link to existing alumni, outcome=linked."""
        row = _make_row(raw_linkedin_url="https://linkedin.com/in/budi")
        program = _make_program()
        company = _make_company()
        existing_alumni = _make_alumni(alumni_id=7)
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, CareerRecord):
                    obj.career_record_id = 55

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=existing_alumni),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            result = commit_staging_row(
                row, snapshot_id=1, source_id=1, actor_id=10, session=session
            )

        assert result.outcome == CommitOutcome.linked
        assert result.alumni_id == 7
        # No new Alumni added (only CareerRecord)
        alumni_objs = [o for o in added_items if isinstance(o, Alumni)]
        assert len(alumni_objs) == 0

    def test_tier1_clears_previous_is_current(self) -> None:
        """D-020: Tier-1 link must still clear existing is_current before new career record."""
        row = _make_row(raw_linkedin_url="https://linkedin.com/in/budi")
        program = _make_program()
        company = _make_company()
        existing_alumni = _make_alumni(alumni_id=7)
        session = _make_session()

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, CareerRecord):
                    obj.career_record_id = 55

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=existing_alumni),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career") as mock_clear,
        ):
            commit_staging_row(row, snapshot_id=1, source_id=1, actor_id=10, session=session)

        mock_clear.assert_called_once_with(7, session)


class TestCommitStagingRowTier2:
    def test_tier2_match_returns_pending_dedup(self) -> None:
        """D-045: Tier-2 match with no resolution → outcome=pending_dedup."""
        row = _make_row()
        program = _make_program()
        company = _make_company()
        existing_alumni = _make_alumni(alumni_id=3)
        session = _make_session()
        session.scalar.return_value = None  # no DedupCandidate yet

        added_items: list = []

        def _add(obj):
            added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, DedupCandidate):
                    obj.dedup_candidate_id = 77

        session.add.side_effect = _add
        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[existing_alumni]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
        ):
            result = commit_staging_row(
                row, snapshot_id=1, source_id=1, actor_id=10, session=session
            )

        assert result.outcome == CommitOutcome.pending_dedup
        assert result.alumni_id is None

    def test_tier2_merge_resolution_links_alumni(self) -> None:
        """Tier-2 'merge' resolution → auto-link to existing alumni."""
        row = _make_row()
        program = _make_program()
        company = _make_company()
        existing_alumni = _make_alumni(alumni_id=3)
        session = _make_session()

        # Simulate existing DedupCandidate with resolution="merge"
        resolved_candidate = MagicMock(spec=DedupCandidate)
        resolved_candidate.dedup_candidate_id = 77
        resolved_candidate.resolution = "merge"
        session.scalar.return_value = resolved_candidate

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, CareerRecord):
                    obj.career_record_id = 88

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[existing_alumni]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            result = commit_staging_row(
                row, snapshot_id=1, source_id=1, actor_id=10, session=session
            )

        assert result.outcome == CommitOutcome.linked
        assert result.alumni_id == 3

    def test_tier2_keep_separate_creates_new_alumni(self) -> None:
        """Tier-2 'keep_separate' resolution → creates new alumni row."""
        row = _make_row()
        program = _make_program()
        company = _make_company()
        existing_alumni = _make_alumni(alumni_id=3)
        session = _make_session()

        resolved_candidate = MagicMock(spec=DedupCandidate)
        resolved_candidate.dedup_candidate_id = 77
        resolved_candidate.resolution = "keep_separate"
        session.scalar.return_value = resolved_candidate

        added_items: list = []
        session.add.side_effect = lambda obj: added_items.append(obj)

        def _flush():
            for obj in added_items:
                if isinstance(obj, Alumni):
                    obj.alumni_id = 99
                elif isinstance(obj, CareerRecord):
                    obj.career_record_id = 101

        session.flush.side_effect = _flush

        with (
            patch(f"{_PATCH_BASE}.match_program", return_value=program),
            patch(f"{_PATCH_BASE}.resolve_company", return_value=company),
            patch(f"{_PATCH_BASE}.find_by_linkedin_url", return_value=None),
            patch(f"{_PATCH_BASE}.find_candidates_by_key", return_value=[existing_alumni]),
            patch(f"{_PATCH_BASE}.write_audit_entry"),
            patch(f"{_PATCH_BASE}._clear_current_career"),
        ):
            result = commit_staging_row(
                row, snapshot_id=1, source_id=1, actor_id=10, session=session
            )

        assert result.outcome == CommitOutcome.created
        alumni_objs = [o for o in added_items if isinstance(o, Alumni)]
        assert len(alumni_objs) == 1


# ---------------------------------------------------------------------------
# commit_batch
# ---------------------------------------------------------------------------


class TestCommitBatch:
    def test_raises_if_batch_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        with pytest.raises(ValueError, match="ImportBatch"):
            commit_batch(batch_id=99, snapshot_id=1, actor_id=10, session=session)

    def test_processes_all_rows(self) -> None:
        rows = [_make_row(staging_row_id=i) for i in range(1, 4)]
        batch = _make_batch()
        session = _make_session()
        session.get.return_value = batch

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = rows
        session.scalars.return_value = scalars_mock

        mock_result = CommitResult(staging_row_id=1, outcome=CommitOutcome.created)
        with patch(f"{_PATCH_BASE}.commit_staging_row", return_value=mock_result) as mock_csr:
            results = commit_batch(batch_id=10, snapshot_id=1, actor_id=10, session=session)

        assert len(results) == 3
        assert mock_csr.call_count == 3

    def test_does_not_commit(self) -> None:
        rows = [_make_row()]
        batch = _make_batch()
        session = _make_session()
        session.get.return_value = batch
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = rows
        session.scalars.return_value = scalars_mock

        mock_result = CommitResult(staging_row_id=1, outcome=CommitOutcome.created)
        with patch(f"{_PATCH_BASE}.commit_staging_row", return_value=mock_result):
            commit_batch(batch_id=10, snapshot_id=1, actor_id=10, session=session)

        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


def _client(session: MagicMock, user: AuthenticatedUser = _CURATOR) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=True)


class TestCommitApi:
    def test_commit_batch_200(self) -> None:
        session = _make_session()
        mock_results = [
            CommitResult(
                staging_row_id=1,
                outcome=CommitOutcome.created,
                alumni_id=10,
                career_record_id=5,
            ),
        ]
        with patch("app.api.commit.commit_batch", return_value=mock_results):
            resp = _client(session).post("/api/v1/commit", json={"batch_id": 10, "snapshot_id": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["created"] == 1

    def test_commit_batch_requires_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).post(
            "/api/v1/commit", json={"batch_id": 10, "snapshot_id": 3}
        )
        assert resp.status_code == 403

    def test_commit_batch_400_on_value_error(self) -> None:
        session = _make_session()
        with patch(
            "app.api.commit.commit_batch",
            side_effect=ValueError("ImportBatch 99 not found."),
        ):
            resp = _client(session).post("/api/v1/commit", json={"batch_id": 99, "snapshot_id": 1})
        assert resp.status_code == 400


class TestValidateAlumniApi:
    def test_validate_returns_200(self) -> None:
        alumni = _make_alumni(alumni_id=5)
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry"):
            resp = _client(session).post("/api/v1/alumni/5/validate", json={"action": "validate"})
        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "validated"

    def test_reject_returns_200(self) -> None:
        alumni = _make_alumni(alumni_id=5)
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry"):
            resp = _client(session).post(
                "/api/v1/alumni/5/validate",
                json={"action": "reject", "reason": "not FTMM"},
            )
        assert resp.status_code == 200
        assert resp.json()["validation_status"] == "rejected"

    def test_invalid_action_400(self) -> None:
        alumni = _make_alumni(alumni_id=5)
        session = _make_session()
        session.get.return_value = alumni
        resp = _client(session).post("/api/v1/alumni/5/validate", json={"action": "approve"})
        assert resp.status_code == 400

    def test_alumni_not_found_404(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).post("/api/v1/alumni/999/validate", json={"action": "validate"})
        assert resp.status_code == 404

    def test_requires_alumni_validate_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).post(
            "/api/v1/alumni/5/validate", json={"action": "validate"}
        )
        assert resp.status_code == 403

    def test_validate_writes_audit(self) -> None:
        """D-025: validate action writes audit entry."""
        alumni = _make_alumni(alumni_id=5)
        session = _make_session()
        session.get.return_value = alumni
        with patch("app.api.commit.write_audit_entry") as mock_audit:
            _client(session).post("/api/v1/alumni/5/validate", json={"action": "validate"})
        mock_audit.assert_called_once()

    def test_only_curator_can_validate_d024(self) -> None:
        """D-024: alumni:validate permission required to change status to validated."""
        viewer = AuthenticatedUser(
            user_id=5,
            supabase_uuid="cccccccc-cccc-cccc-cccc-cccccccccccc",
            role_name="Faculty Viewer",
            permissions=frozenset(["alumni:read"]),
        )
        session = _make_session()
        resp = _client(session, user=viewer).post(
            "/api/v1/alumni/5/validate", json={"action": "validate"}
        )
        assert resp.status_code == 403


class TestGetAlumniApi:
    def test_get_200(self) -> None:
        alumni = _make_alumni(alumni_id=5)
        session = _make_session()
        session.get.return_value = alumni
        resp = _client(session).get("/api/v1/alumni/5")
        assert resp.status_code == 200
        assert resp.json()["alumni_id"] == 5

    def test_get_404(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).get("/api/v1/alumni/999")
        assert resp.status_code == 404

    def test_get_requires_alumni_read(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/alumni/5")
        assert resp.status_code == 403


class TestListAlumniApi:
    def test_list_200(self) -> None:
        a1 = _make_alumni(alumni_id=1)
        a2 = _make_alumni(alumni_id=2, validation_status="validated")
        session = _make_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [a1, a2]
        session.scalars.return_value = scalars_mock
        resp = _client(session).get("/api/v1/alumni")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_by_status(self) -> None:
        a1 = _make_alumni(alumni_id=1, validation_status="pending")
        session = _make_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [a1]
        session.scalars.return_value = scalars_mock
        resp = _client(session).get("/api/v1/alumni?validation_status=pending")
        assert resp.status_code == 200

    def test_invalid_status_400(self) -> None:
        session = _make_session()
        resp = _client(session).get("/api/v1/alumni?validation_status=unknown")
        assert resp.status_code == 400

    def test_requires_alumni_read(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/alumni")
        assert resp.status_code == 403
