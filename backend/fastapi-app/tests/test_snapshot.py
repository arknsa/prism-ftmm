"""Tests for snapshot.py service + snapshots API endpoint (P4.4).

Covers:
- open_snapshot: valid creation, duplicate detection, label validation
- get_snapshot: found, not found
- get_snapshot_by_label: found, not found
- list_snapshots: returns all
- API: POST/GET endpoints, permission guards, audit wiring
- D-021: one snapshot per quarter_label
- D-031: no auto-commit; caller owns transaction
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.snapshot import RefreshSnapshot
from app.schemas.auth import AuthenticatedUser
from app.services.snapshot import (
    get_snapshot,
    get_snapshot_by_label,
    list_snapshots,
    open_snapshot,
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
            "company:read",
            "company:write",
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


def _make_snapshot(
    snapshot_id: int = 1,
    quarter_label: str = "2025-Q1",
    refresh_date: datetime.date | None = None,
    notes: str | None = None,
) -> MagicMock:
    s = MagicMock(spec=RefreshSnapshot)
    s.snapshot_id = snapshot_id
    s.quarter_label = quarter_label
    s.refresh_date = refresh_date or datetime.date(2025, 3, 31)
    s.notes = notes
    s.created_at = datetime.datetime(2025, 3, 31, tzinfo=datetime.UTC)
    return s


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
# open_snapshot
# ===========================================================================


class TestOpenSnapshot:
    def test_creates_new_snapshot(self) -> None:
        session = _make_session(scalar_return=None)
        snap = open_snapshot("2025-Q1", session=session)
        session.add.assert_called_once()
        assert snap.quarter_label == "2025-Q1"

    def test_defaults_refresh_date_to_today(self) -> None:
        session = _make_session(scalar_return=None)
        snap = open_snapshot("2025-Q2", session=session)
        assert snap.refresh_date == datetime.date.today()

    def test_custom_refresh_date(self) -> None:
        session = _make_session(scalar_return=None)
        snap = open_snapshot("2025-Q3", refresh_date=datetime.date(2025, 9, 30), session=session)
        assert snap.refresh_date == datetime.date(2025, 9, 30)

    def test_notes_stored(self) -> None:
        session = _make_session(scalar_return=None)
        snap = open_snapshot("2025-Q4", notes="Annual refresh", session=session)
        assert snap.notes == "Annual refresh"

    def test_duplicate_label_raises(self) -> None:
        existing = _make_snapshot()
        session = _make_session(scalar_return=existing)
        with pytest.raises(ValueError, match="already exists"):
            open_snapshot("2025-Q1", session=session)

    def test_invalid_label_format_raises(self) -> None:
        session = _make_session(scalar_return=None)
        with pytest.raises(ValueError, match="Invalid quarter_label"):
            open_snapshot("Q1-2025", session=session)

    def test_invalid_label_q5_raises(self) -> None:
        session = _make_session(scalar_return=None)
        with pytest.raises(ValueError, match="Invalid quarter_label"):
            open_snapshot("2025-Q5", session=session)

    def test_does_not_commit(self) -> None:
        session = _make_session(scalar_return=None)
        open_snapshot("2025-Q1", session=session)
        session.commit.assert_not_called()

    @pytest.mark.parametrize(
        "label",
        ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2024-Q4"],
    )
    def test_valid_labels_accepted(self, label: str) -> None:
        session = _make_session(scalar_return=None)
        snap = open_snapshot(label, session=session)
        assert snap.quarter_label == label

    @pytest.mark.parametrize(
        "bad_label",
        ["2025-Q0", "2025-Q5", "Q1-2025", "2025Q1", "2025-q1", "2025-01", ""],
    )
    def test_invalid_labels_rejected(self, bad_label: str) -> None:
        session = _make_session(scalar_return=None)
        with pytest.raises(ValueError):
            open_snapshot(bad_label, session=session)


# ===========================================================================
# get_snapshot / get_snapshot_by_label
# ===========================================================================


class TestGetSnapshot:
    def test_found_by_id(self) -> None:
        snap = _make_snapshot()
        session = _make_session(get_return=snap)
        assert get_snapshot(1, session) is snap

    def test_not_found_by_id(self) -> None:
        session = _make_session(get_return=None)
        assert get_snapshot(999, session) is None

    def test_found_by_label(self) -> None:
        snap = _make_snapshot()
        session = _make_session(scalar_return=snap)
        assert get_snapshot_by_label("2025-Q1", session) is snap

    def test_not_found_by_label(self) -> None:
        session = _make_session(scalar_return=None)
        assert get_snapshot_by_label("2099-Q1", session) is None


# ===========================================================================
# list_snapshots
# ===========================================================================


class TestListSnapshots:
    def test_returns_all(self) -> None:
        s1 = _make_snapshot(snapshot_id=1, quarter_label="2025-Q1")
        s2 = _make_snapshot(snapshot_id=2, quarter_label="2025-Q2")
        session = _make_session(scalars_return=[s1, s2])
        result = list_snapshots(session)
        assert s1 in result
        assert s2 in result

    def test_empty_when_none(self) -> None:
        session = _make_session(scalars_return=[])
        assert list_snapshots(session) == []


# ===========================================================================
# API endpoints
# ===========================================================================


def _client(session: MagicMock, user: AuthenticatedUser = _CURATOR) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=True)


class TestSnapshotApi:
    # --- POST /snapshots ---

    def test_create_snapshot_201(self) -> None:
        snap = _make_snapshot()
        session = _make_session(scalar_return=None)
        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry"),
        ):
            resp = _client(session).post(
                "/api/v1/snapshots",
                json={"quarter_label": "2025-Q1"},
            )
        assert resp.status_code == 201

    def test_create_snapshot_duplicate_400(self) -> None:
        session = _make_session()
        with patch(
            "app.api.snapshots.open_snapshot",
            side_effect=ValueError("already exists"),
        ):
            resp = _client(session).post(
                "/api/v1/snapshots",
                json={"quarter_label": "2025-Q1"},
            )
        assert resp.status_code == 400

    def test_create_snapshot_requires_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).post(
            "/api/v1/snapshots",
            json={"quarter_label": "2025-Q1"},
        )
        assert resp.status_code == 403

    def test_create_snapshot_writes_audit(self) -> None:
        snap = _make_snapshot()
        session = _make_session(scalar_return=None)
        with (
            patch("app.api.snapshots.open_snapshot", return_value=snap),
            patch("app.api.snapshots.write_audit_entry") as mock_audit,
        ):
            _client(session).post("/api/v1/snapshots", json={"quarter_label": "2025-Q1"})
        mock_audit.assert_called_once()

    # --- GET /snapshots ---

    def test_list_snapshots_200(self) -> None:
        s1 = _make_snapshot(snapshot_id=1)
        s2 = _make_snapshot(snapshot_id=2, quarter_label="2025-Q2")
        session = _make_session(scalars_return=[s1, s2])
        resp = _client(session).get("/api/v1/snapshots")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_requires_permission(self) -> None:
        session = _make_session(scalars_return=[])
        resp = _client(session, user=_NO_PERM).get("/api/v1/snapshots")
        assert resp.status_code == 403

    # --- GET /snapshots/{id} ---

    def test_get_snapshot_200(self) -> None:
        snap = _make_snapshot(snapshot_id=7)
        session = _make_session(get_return=snap)
        resp = _client(session).get("/api/v1/snapshots/7")
        assert resp.status_code == 200
        assert resp.json()["snapshot_id"] == 7

    def test_get_snapshot_404(self) -> None:
        session = _make_session(get_return=None)
        resp = _client(session).get("/api/v1/snapshots/999")
        assert resp.status_code == 404
