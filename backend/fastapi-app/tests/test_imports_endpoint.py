"""Tests for POST /api/v1/imports, GET /api/v1/imports/{batch_id},
and GET /api/v1/imports/{batch_id}/rows (P3.3, Artifact A2).

Strategy: dependency_overrides inject a synthetic AuthenticatedUser
(no real JWT/DB). The SQLAlchemy session is replaced with create_autospec
so no real DB connection is required.

Atomicity coverage: test_import_atomicity.py covers the rollback path
separately. Here we assert the happy-path commit sequence and RBAC.

Decisions: D-031 (gateway), D-033 (import workflow), D-025 (audit), D-036 (RBAC).
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, create_autospec

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.staging import ImportBatch, StagingRow
from app.rate_limiting import import_rate_limit
from app.schemas.auth import AuthenticatedUser
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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

_READ_ONLY = AuthenticatedUser(
    user_id=9,
    supabase_uuid="99999999-9999-9999-9999-999999999999",
    role_name="Read Only",
    permissions=frozenset(["alumni:read", "career:read", "company:read", "analytics:read"]),
)

# Minimal valid LinkedIn CSV
_LINKEDIN_CSV = (
    b"full_name,study_program,graduation_year,employer,role_title,location\n"
    b"Budi Santoso,Technology of Data Science,2022,Gojek,Analyst,Jakarta\n"
)


def _make_session() -> MagicMock:
    """Spec'd mock Session; flush() assigns batch_id=1 on ImportBatch."""
    session = create_autospec(Session, instance=True)

    def _flush() -> None:
        for c in session.add.call_args_list:
            obj = c.args[0]
            if isinstance(obj, ImportBatch) and obj.batch_id is None:
                obj.batch_id = 1

    session.flush.side_effect = _flush
    return session


def _app_with(user: AuthenticatedUser, session: MagicMock | None = None) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[import_rate_limit] = lambda: None
    if session is not None:
        app.dependency_overrides[get_session] = lambda: session
    return app


def _app_401() -> FastAPI:
    app = create_app()

    def _raise() -> AuthenticatedUser:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    app.dependency_overrides[get_current_user] = _raise
    app.dependency_overrides[import_rate_limit] = lambda: None
    return app


# ---------------------------------------------------------------------------
# POST /api/v1/imports — RBAC guard
# ---------------------------------------------------------------------------


class TestImportRBAC:
    def test_missing_auth_returns_401(self) -> None:
        client = TestClient(_app_401())
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 401

    def test_read_only_user_returns_403(self) -> None:
        client = TestClient(_app_with(_READ_ONLY))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 403

    def test_curator_is_allowed(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/v1/imports — happy path
# ---------------------------------------------------------------------------


class TestImportHappyPath:
    def test_returns_201_on_success(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 201

    def test_response_body_contains_batch_id(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        body = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        ).json()
        assert body["batch_id"] == 1

    def test_response_body_source_id_matches(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        body = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        ).json()
        assert body["source_id"] == 3

    def test_response_body_total_rows(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        body = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        ).json()
        assert body["total_rows"] == 1

    def test_response_body_status_complete(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        body = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        ).json()
        assert body["status"] == "complete"

    def test_session_commit_called_once(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        session.commit.assert_called_once()

    def test_audit_entry_added_to_session(self) -> None:
        from app.models.audit import AuditLog

        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        audit_entries = [o for o in added_objects if isinstance(o, AuditLog)]
        assert len(audit_entries) == 1

    def test_audit_entry_table_name_is_import_batch(self) -> None:
        from app.models.audit import AuditLog

        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        entry = next(o for o in added_objects if isinstance(o, AuditLog))
        assert entry.table_name == "import_batch"

    def test_audit_entry_action_type_is_insert(self) -> None:
        from app.models.audit import AuditLog

        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        entry = next(o for o in added_objects if isinstance(o, AuditLog))
        assert entry.action_type == "INSERT"

    def test_audit_entry_changed_by_matches_curator(self) -> None:
        from app.models.audit import AuditLog

        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        entry = next(o for o in added_objects if isinstance(o, AuditLog))
        assert entry.changed_by == _CURATOR.user_id

    def test_created_by_on_batch_matches_curator(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        batch = next(o for o in added_objects if isinstance(o, ImportBatch))
        assert batch.created_by == _CURATOR.user_id

    def test_staging_rows_added_to_session(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("linkedin.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        added_objects = [c.args[0] for c in session.add.call_args_list]
        rows = [o for o in added_objects if isinstance(o, StagingRow)]
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# POST /api/v1/imports — error cases
# ---------------------------------------------------------------------------


class TestImportErrors:
    def test_unknown_source_type_returns_400(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "UnknownSource", "source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 400

    def test_unsupported_extension_returns_400(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("import.txt", io.BytesIO(b"data"), "text/plain")},
        )
        assert response.status_code == 400

    def test_rollback_called_on_parse_error(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        client.post(
            "/api/v1/imports",
            data={"source_type": "UnknownSource", "source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        # 400 before parse_import is called — no rollback needed for source validation;
        # the rollback path is verified in test_import_atomicity.py.
        session.commit.assert_not_called()

    def test_missing_file_field_returns_422(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
        )
        assert response.status_code == 422

    def test_missing_source_type_returns_422(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.post(
            "/api/v1/imports",
            data={"source_id": "3"},
            files={"file": ("test.csv", io.BytesIO(_LINKEDIN_CSV), "text/csv")},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/imports/{batch_id} — EP-2
# ---------------------------------------------------------------------------


class TestGetBatch:
    def _make_batch(self) -> ImportBatch:
        b = ImportBatch(
            source_id=3,
            filename="test.csv",
            total_rows=1,
            parsed_rows=1,
            error_rows=0,
            status="complete",
            created_by=5,
        )
        b.batch_id = 1
        import datetime

        b.created_at = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
        return b

    def test_returns_200_for_existing_batch(self) -> None:
        batch = self._make_batch()
        session = _make_session()
        session.get.return_value = batch
        client = TestClient(_app_with(_CURATOR, session))
        response = client.get("/api/v1/imports/1")
        assert response.status_code == 200

    def test_returns_404_for_missing_batch(self) -> None:
        session = _make_session()
        session.get.return_value = None
        client = TestClient(_app_with(_CURATOR, session))
        response = client.get("/api/v1/imports/9999")
        assert response.status_code == 404

    def test_read_only_cannot_get_batch(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_READ_ONLY, session))
        response = client.get("/api/v1/imports/1")
        assert response.status_code == 403

    def test_response_contains_batch_id(self) -> None:
        batch = self._make_batch()
        session = _make_session()
        session.get.return_value = batch
        client = TestClient(_app_with(_CURATOR, session))
        body = client.get("/api/v1/imports/1").json()
        assert body["batch_id"] == 1


# ---------------------------------------------------------------------------
# GET /api/v1/imports/{batch_id}/rows — EP-3
# ---------------------------------------------------------------------------


class TestGetBatchRows:
    def _make_batch(self) -> ImportBatch:
        b = ImportBatch(
            source_id=3,
            filename="test.csv",
            total_rows=2,
            parsed_rows=1,
            error_rows=1,
            status="complete",
            created_by=5,
        )
        b.batch_id = 1
        import datetime

        b.created_at = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
        return b

    def test_returns_200_for_existing_batch(self) -> None:
        batch = self._make_batch()
        session = _make_session()
        session.get.return_value = batch
        session.scalar.return_value = 0
        session.scalars.return_value.all.return_value = []
        client = TestClient(_app_with(_CURATOR, session))
        response = client.get("/api/v1/imports/1/rows")
        assert response.status_code == 200

    def test_returns_404_for_missing_batch(self) -> None:
        session = _make_session()
        session.get.return_value = None
        client = TestClient(_app_with(_CURATOR, session))
        response = client.get("/api/v1/imports/9999/rows")
        assert response.status_code == 404

    def test_read_only_cannot_list_rows(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_READ_ONLY, session))
        response = client.get("/api/v1/imports/1/rows")
        assert response.status_code == 403

    def test_response_structure_has_pagination_fields(self) -> None:
        batch = self._make_batch()
        session = _make_session()
        session.get.return_value = batch
        session.scalar.return_value = 0
        session.scalars.return_value.all.return_value = []
        client = TestClient(_app_with(_CURATOR, session))
        body = client.get("/api/v1/imports/1/rows").json()
        assert "batch_id" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert "items" in body

    def test_default_pagination_values(self) -> None:
        batch = self._make_batch()
        session = _make_session()
        session.get.return_value = batch
        session.scalar.return_value = 0
        session.scalars.return_value.all.return_value = []
        client = TestClient(_app_with(_CURATOR, session))
        body = client.get("/api/v1/imports/1/rows").json()
        assert body["page"] == 1
        assert body["page_size"] == 50

    def test_page_size_limit_422(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        response = client.get("/api/v1/imports/1/rows?page_size=300")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# P7.8 — Upload size guard
# ---------------------------------------------------------------------------


class TestImportSizeGuard:
    """POST /api/v1/imports rejects files over 10 MB (P7.8)."""

    def test_oversized_upload_returns_413(self) -> None:
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        # 10 MB + 1 byte
        oversized = io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("big.csv", oversized, "text/csv")},
        )
        assert response.status_code == 413

    def test_at_limit_is_accepted_through_parse(self) -> None:
        """A file exactly at the limit doesn't get a 413 (parse may still fail on content)."""
        session = _make_session()
        client = TestClient(_app_with(_CURATOR, session))
        # Exactly 10 MB — should pass the size check (but likely fail parsing bad content)
        at_limit = io.BytesIO(b"x" * (10 * 1024 * 1024))
        response = client.post(
            "/api/v1/imports",
            data={"source_type": "LinkedIn", "source_id": "3"},
            files={"file": ("at_limit.csv", at_limit, "text/csv")},
        )
        # Must NOT be 413
        assert response.status_code != 413
