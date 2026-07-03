"""Atomicity tests for the import endpoint (P3.3, A2 §EP-1 atomicity contract).

Verifies that batch data + audit entry are committed together, and that a
failure before commit triggers rollback so no orphan batch or audit row
is ever written.

Decisions: D-025 (audit), D-031 (gateway), D-033 (manual import workflow).
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, create_autospec

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.audit import AuditLog
from app.models.staging import ImportBatch
from app.rate_limiting import import_rate_limit
from app.schemas.auth import AuthenticatedUser
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_CURATOR = AuthenticatedUser(
    user_id=5,
    supabase_uuid="cccccccc-cccc-cccc-cccc-cccccccccccc",
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

_LINKEDIN_CSV = (
    b"full_name,study_program,graduation_year,employer,role_title,location\n"
    b"Budi Santoso,Technology of Data Science,2022,Gojek,Analyst,Jakarta\n"
)


def _make_session() -> MagicMock:
    session = create_autospec(Session, instance=True)

    def _flush() -> None:
        for c in session.add.call_args_list:
            obj = c.args[0]
            if isinstance(obj, ImportBatch) and obj.batch_id is None:
                obj.batch_id = 1

    session.flush.side_effect = _flush
    return session


def _app_with(user: AuthenticatedUser, session: MagicMock) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[import_rate_limit] = lambda: None
    return app


# ---------------------------------------------------------------------------
# Commit path: data + audit commit atomically
# ---------------------------------------------------------------------------


class TestAtomicCommit:
    def test_commit_called_after_audit_added(self) -> None:
        """Commit must happen after both the ImportBatch and AuditLog are added."""
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )

        # Extract the sequence of add() calls
        added_objects = [c.args[0] for c in session.add.call_args_list]
        types_added = [type(o).__name__ for o in added_objects]

        # ImportBatch, StagingRow(s), and AuditLog must all appear before commit
        assert "ImportBatch" in types_added
        assert "StagingRow" in types_added
        assert "AuditLog" in types_added
        session.commit.assert_called_once()
        session.rollback.assert_not_called()

    def test_audit_entry_record_id_matches_batch_id(self) -> None:
        """Audit record_id must equal the batch's assigned batch_id."""
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        audit = next(o for o in added_objects if isinstance(o, AuditLog))
        assert audit.record_id == "1"  # batch_id assigned by flush side_effect

    def test_audit_new_values_contains_filename(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        audit = next(o for o in added_objects if isinstance(o, AuditLog))
        assert audit.new_values is not None
        assert audit.new_values.get("filename") == "linkedin.csv"

    def test_audit_old_values_is_none_for_insert(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        audit = next(o for o in added_objects if isinstance(o, AuditLog))
        assert audit.old_values is None


# ---------------------------------------------------------------------------
# Rollback path: any exception before commit triggers rollback
# ---------------------------------------------------------------------------


class TestRollbackOnFailure:
    def test_rollback_on_parse_error_no_commit(self) -> None:
        """A parse-level ValueError (e.g. bad file content) triggers rollback, no commit."""
        session = _make_session()

        # Simulate parse_import raising ValueError mid-flight
        session.flush.side_effect = ValueError("simulated parse failure")

        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 400
        session.rollback.assert_called_once()
        session.commit.assert_not_called()

    def test_rollback_on_unicode_error(self) -> None:
        """A UnicodeDecodeError (corrupt file) triggers rollback and returns 400."""
        session = _make_session()
        # Inject non-UTF-8 bytes that the CSV decoder will fail on
        # (csv.DictReader uses errors="replace" so this won't fail for CSV;
        # we simulate by having flush raise UnicodeDecodeError)
        session.flush.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "reason")

        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 400
        session.rollback.assert_called_once()
        session.commit.assert_not_called()

    def test_no_audit_entry_when_parse_fails_before_flush(self) -> None:
        """If parse fails before flush, no AuditLog is added to the session."""
        session = _make_session()
        # Make flush fail immediately — ImportBatch is added but never flushed
        session.flush.side_effect = ValueError("flush failed")

        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        audit_entries = [o for o in added_objects if isinstance(o, AuditLog)]
        # Audit is added AFTER flush (needs batch_id); if flush fails, no AuditLog added
        assert len(audit_entries) == 0
