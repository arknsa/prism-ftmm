"""Tests for dedup_queue.py + dedup API endpoint (P4.3).

Covers:
- enqueue_candidate: create, idempotent re-enqueue of pending
- resolve_candidate: merge, keep_separate, already-resolved error, not-found error
- get_pending_candidates: returns only pending
- get_candidate: found / not found
- API: list, get, resolve (success + error cases)
- D-024: only curator can resolve (permission guard)
- D-025: audit entry written on resolve
- D-045: no auto-merge; every Tier-2 requires human decision
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.dedup import DedupCandidate
from app.schemas.auth import AuthenticatedUser
from app.services.dedup_queue import (
    enqueue_candidate,
    get_candidate,
    get_pending_candidates,
    resolve_candidate,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Shared fixtures
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

_NO_DEDUP_PERM = AuthenticatedUser(
    user_id=99,
    supabase_uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    role_name="Faculty Viewer",
    permissions=frozenset(["analytics:read"]),
)


def _make_candidate(
    dedup_candidate_id: int = 1,
    staging_row_id: int = 100,
    matched_alumni_id: int = 200,
    resolution: str = "pending",
    resolved_by: int | None = None,
    resolved_at: datetime.datetime | None = None,
) -> MagicMock:
    c = MagicMock(spec=DedupCandidate)
    c.dedup_candidate_id = dedup_candidate_id
    c.staging_row_id = staging_row_id
    c.matched_alumni_id = matched_alumni_id
    c.resolution = resolution
    c.resolved_by = resolved_by
    c.resolved_at = resolved_at
    c.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return c


def _make_session(
    scalar_return: object = None,
    scalars_return: list[object] | None = None,
    get_return: object = None,
) -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = scalar_return
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_return or []
    session.scalars.return_value = scalars_mock
    session.get.return_value = get_return
    return session


# ===========================================================================
# enqueue_candidate
# ===========================================================================


class TestEnqueueCandidate:
    def test_creates_new_candidate(self) -> None:
        session = _make_session(scalar_return=None)
        enqueue_candidate(100, 200, session)
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.staging_row_id == 100
        assert added.matched_alumni_id == 200
        assert added.resolution == "pending"

    def test_idempotent_returns_existing(self) -> None:
        existing = _make_candidate()
        session = _make_session(scalar_return=existing)
        result = enqueue_candidate(100, 200, session)
        assert result is existing
        session.add.assert_not_called()

    def test_does_not_commit(self) -> None:
        session = _make_session(scalar_return=None)
        enqueue_candidate(100, 200, session)
        session.commit.assert_not_called()


# ===========================================================================
# resolve_candidate
# ===========================================================================


class TestResolveCandidate:
    def test_resolve_merge(self) -> None:
        candidate = _make_candidate()
        session = _make_session(get_return=candidate)
        result = resolve_candidate(1, "merge", resolved_by=10, session=session)
        assert result.resolution == "merge"
        assert result.resolved_by == 10
        assert result.resolved_at is not None

    def test_resolve_keep_separate(self) -> None:
        candidate = _make_candidate()
        session = _make_session(get_return=candidate)
        result = resolve_candidate(1, "keep_separate", resolved_by=10, session=session)
        assert result.resolution == "keep_separate"

    def test_not_found_raises(self) -> None:
        session = _make_session(get_return=None)
        with pytest.raises(ValueError, match="not found"):
            resolve_candidate(999, "merge", resolved_by=10, session=session)

    def test_already_resolved_raises(self) -> None:
        candidate = _make_candidate(resolution="merge")
        session = _make_session(get_return=candidate)
        with pytest.raises(ValueError, match="already resolved"):
            resolve_candidate(1, "keep_separate", resolved_by=10, session=session)

    def test_invalid_resolution_raises(self) -> None:
        candidate = _make_candidate()
        session = _make_session(get_return=candidate)
        with pytest.raises(ValueError, match="Invalid resolution"):
            resolve_candidate(1, "auto_merge", resolved_by=10, session=session)

    def test_does_not_commit(self) -> None:
        candidate = _make_candidate()
        session = _make_session(get_return=candidate)
        resolve_candidate(1, "merge", resolved_by=10, session=session)
        session.commit.assert_not_called()


# ===========================================================================
# get_pending_candidates
# ===========================================================================


class TestGetPendingCandidates:
    def test_returns_pending_list(self) -> None:
        c1 = _make_candidate(dedup_candidate_id=1)
        c2 = _make_candidate(dedup_candidate_id=2)
        session = _make_session(scalars_return=[c1, c2])
        result = get_pending_candidates(session)
        assert c1 in result
        assert c2 in result

    def test_empty_when_none(self) -> None:
        session = _make_session(scalars_return=[])
        assert get_pending_candidates(session) == []


# ===========================================================================
# get_candidate
# ===========================================================================


class TestGetCandidate:
    def test_found(self) -> None:
        candidate = _make_candidate()
        session = _make_session(get_return=candidate)
        result = get_candidate(1, session)
        assert result is candidate

    def test_not_found(self) -> None:
        session = _make_session(get_return=None)
        result = get_candidate(999, session)
        assert result is None


# ===========================================================================
# API endpoints
# ===========================================================================


def _build_app(session: MagicMock, user: AuthenticatedUser) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class TestDedupApi:
    def _client(self, session: MagicMock, user: AuthenticatedUser = _CURATOR) -> TestClient:
        app = _build_app(session, user)
        return TestClient(app, raise_server_exceptions=True)

    # --- GET /candidates ---

    def test_list_returns_200(self) -> None:
        c = _make_candidate()
        session = _make_session(scalars_return=[c])
        resp = self._client(session).get("/api/v1/dedup/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_empty(self) -> None:
        session = _make_session(scalars_return=[])
        resp = self._client(session).get("/api/v1/dedup/candidates")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_requires_dedup_permission(self) -> None:
        session = _make_session(scalars_return=[])
        resp = self._client(session, user=_NO_DEDUP_PERM).get("/api/v1/dedup/candidates")
        assert resp.status_code == 403

    # --- GET /candidates/{id} ---

    def test_get_candidate_200(self) -> None:
        c = _make_candidate(dedup_candidate_id=5)
        session = _make_session(get_return=c)
        resp = self._client(session).get("/api/v1/dedup/candidates/5")
        assert resp.status_code == 200
        assert resp.json()["dedup_candidate_id"] == 5

    def test_get_candidate_404(self) -> None:
        session = _make_session(get_return=None)
        resp = self._client(session).get("/api/v1/dedup/candidates/999")
        assert resp.status_code == 404

    # --- POST /candidates/{id}/resolve ---

    def test_resolve_merge_200(self) -> None:
        c = _make_candidate()
        session = _make_session(get_return=c)
        with (
            patch("app.api.dedup.resolve_candidate", return_value=c) as mock_resolve,
            patch("app.api.dedup.write_audit_entry"),
        ):
            resp = self._client(session).post(
                "/api/v1/dedup/candidates/1/resolve",
                json={"resolution": "merge"},
            )
        assert resp.status_code == 200
        mock_resolve.assert_called_once()

    def test_resolve_invalid_resolution_400(self) -> None:
        c = _make_candidate()
        session = _make_session(get_return=c)
        with patch(
            "app.api.dedup.resolve_candidate",
            side_effect=ValueError("Invalid resolution"),
        ):
            resp = self._client(session).post(
                "/api/v1/dedup/candidates/1/resolve",
                json={"resolution": "auto_merge"},
            )
        assert resp.status_code == 400

    def test_resolve_requires_permission(self) -> None:
        session = _make_session(get_return=_make_candidate())
        resp = self._client(session, user=_NO_DEDUP_PERM).post(
            "/api/v1/dedup/candidates/1/resolve",
            json={"resolution": "merge"},
        )
        assert resp.status_code == 403

    def test_resolve_writes_audit(self) -> None:
        c = _make_candidate()
        session = _make_session(get_return=c)
        with (
            patch("app.api.dedup.resolve_candidate", return_value=c),
            patch("app.api.dedup.write_audit_entry") as mock_audit,
        ):
            self._client(session).post(
                "/api/v1/dedup/candidates/1/resolve",
                json={"resolution": "merge"},
            )
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args
        assert kwargs[1]["table_name"] == "dedup_candidate" or kwargs[0][1] == "dedup_candidate"
