"""Tests for company and alias management endpoints (P4.6, P4.10 backend).

Covers:
- GET /companies — list, permission guard
- GET /companies/{id} — found, 404
- PATCH /companies/{id} — update industry/location, audit, 404, permission
- GET /companies/{id}/aliases — list aliases, 404
- GET /aliases/{id} — found, 404
- PATCH /aliases/{id}/remap — remap, audit, 404 alias, 400 bad target, permission
- D-025: all mutations write AUDIT_LOG
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, create_autospec, patch

from app.db import get_session
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.company import Company, CompanyAlias
from app.schemas.auth import AuthenticatedUser
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
            "company:read",
            "company:write",
            "import:run",
        ]
    ),
)

_READ_ONLY = AuthenticatedUser(
    user_id=20,
    supabase_uuid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    role_name="Faculty Viewer",
    permissions=frozenset(["company:read", "analytics:read"]),
)

_NO_PERM = AuthenticatedUser(
    user_id=99,
    supabase_uuid="cccccccc-cccc-cccc-cccc-cccccccccccc",
    role_name="External",
    permissions=frozenset(["analytics:read"]),
)


def _make_company(
    company_id: int = 1,
    canonical_name: str = "PT Maju Jaya",
    industry_id: int | None = None,
    location_id: int | None = None,
) -> MagicMock:
    c = MagicMock(spec=Company)
    c.company_id = company_id
    c.canonical_name = canonical_name
    c.industry_id = industry_id
    c.location_id = location_id
    c.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return c


def _make_alias(
    alias_id: int = 1,
    company_id: int = 1,
    alias_name: str = "maju jaya",
    source_id: int | None = 2,
) -> MagicMock:
    a = MagicMock(spec=CompanyAlias)
    a.alias_id = alias_id
    a.company_id = company_id
    a.alias_name = alias_name
    a.source_id = source_id
    a.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return a


def _make_session() -> MagicMock:
    s = create_autospec(Session, instance=True)
    s.get.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    s.scalars.return_value = scalars_mock
    return s


def _client(session: MagicMock, user: AuthenticatedUser = _CURATOR) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=True)


_PATCH_AUDIT = "app.api.company.write_audit_entry"


# ===========================================================================
# GET /api/v1/companies
# ===========================================================================


class TestListCompanies:
    def test_200_empty(self) -> None:
        session = _make_session()
        resp = _client(session).get("/api/v1/companies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_200_returns_companies(self) -> None:
        c1 = _make_company(company_id=1, canonical_name="A")
        c2 = _make_company(company_id=2, canonical_name="B")
        session = _make_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [c1, c2]
        session.scalars.return_value = scalars_mock
        resp = _client(session).get("/api/v1/companies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/companies")
        assert resp.status_code == 403


# ===========================================================================
# GET /api/v1/companies/{company_id}
# ===========================================================================


class TestGetCompany:
    def test_200_found(self) -> None:
        company = _make_company(company_id=5, canonical_name="PT Sejahtera")
        session = _make_session()
        session.get.return_value = company
        resp = _client(session).get("/api/v1/companies/5")
        assert resp.status_code == 200
        assert resp.json()["company_id"] == 5
        assert resp.json()["canonical_name"] == "PT Sejahtera"

    def test_404_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).get("/api/v1/companies/999")
        assert resp.status_code == 404

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/companies/1")
        assert resp.status_code == 403


# ===========================================================================
# PATCH /api/v1/companies/{company_id}
# ===========================================================================


class TestUpdateCompany:
    def test_200_updates_industry(self) -> None:
        company = _make_company(company_id=5)
        session = _make_session()
        session.get.return_value = company
        with patch(_PATCH_AUDIT):
            resp = _client(session).patch("/api/v1/companies/5", json={"industry_id": 7})
        assert resp.status_code == 200
        assert company.industry_id == 7

    def test_200_updates_location(self) -> None:
        company = _make_company(company_id=5)
        session = _make_session()
        session.get.return_value = company
        with patch(_PATCH_AUDIT):
            resp = _client(session).patch("/api/v1/companies/5", json={"location_id": 3})
        assert resp.status_code == 200
        assert company.location_id == 3

    def test_200_both_fields(self) -> None:
        company = _make_company(company_id=5)
        session = _make_session()
        session.get.return_value = company
        with patch(_PATCH_AUDIT):
            resp = _client(session).patch(
                "/api/v1/companies/5", json={"industry_id": 2, "location_id": 4}
            )
        assert resp.status_code == 200
        assert company.industry_id == 2
        assert company.location_id == 4

    def test_writes_audit(self) -> None:
        """D-025: company update writes audit entry."""
        company = _make_company(company_id=5)
        session = _make_session()
        session.get.return_value = company
        with patch(_PATCH_AUDIT) as mock_audit:
            _client(session).patch("/api/v1/companies/5", json={"industry_id": 7})
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["table_name"] == "company"
        assert call_kwargs["action_type"] == "UPDATE"

    def test_404_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).patch("/api/v1/companies/999", json={"industry_id": 7})
        assert resp.status_code == 404

    def test_403_no_write_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_READ_ONLY).patch(
            "/api/v1/companies/5", json={"industry_id": 7}
        )
        assert resp.status_code == 403

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).patch("/api/v1/companies/5", json={"industry_id": 7})
        assert resp.status_code == 403


# ===========================================================================
# GET /api/v1/companies/{company_id}/aliases
# ===========================================================================


class TestListCompanyAliases:
    def test_200_returns_aliases(self) -> None:
        company = _make_company(company_id=1)
        a1 = _make_alias(alias_id=1, company_id=1, alias_name="maju jaya")
        a2 = _make_alias(alias_id=2, company_id=1, alias_name="pt maju jaya")
        session = _make_session()
        session.get.return_value = company
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [a1, a2]
        session.scalars.return_value = scalars_mock
        resp = _client(session).get("/api/v1/companies/1/aliases")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_404_company_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).get("/api/v1/companies/999/aliases")
        assert resp.status_code == 404

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/companies/1/aliases")
        assert resp.status_code == 403


# ===========================================================================
# GET /api/v1/aliases/{alias_id}
# ===========================================================================


class TestGetAlias:
    def test_200_found(self) -> None:
        alias = _make_alias(alias_id=3, alias_name="maju jaya")
        session = _make_session()
        session.get.return_value = alias
        resp = _client(session).get("/api/v1/aliases/3")
        assert resp.status_code == 200
        assert resp.json()["alias_id"] == 3

    def test_404_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).get("/api/v1/aliases/999")
        assert resp.status_code == 404

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).get("/api/v1/aliases/3")
        assert resp.status_code == 403


# ===========================================================================
# PATCH /api/v1/aliases/{alias_id}/remap
# ===========================================================================


class TestRemapAlias:
    def test_200_remaps_alias(self) -> None:
        alias = _make_alias(alias_id=3, company_id=1)
        target_company = _make_company(company_id=2)
        session = _make_session()

        def _get(model, pk):
            if model is CompanyAlias:
                return alias
            if model is Company:
                return target_company
            return None

        session.get.side_effect = _get
        with patch(_PATCH_AUDIT):
            resp = _client(session).patch("/api/v1/aliases/3/remap", json={"company_id": 2})
        assert resp.status_code == 200
        assert alias.company_id == 2

    def test_writes_audit_on_remap(self) -> None:
        """D-025: remap writes audit entry."""
        alias = _make_alias(alias_id=3, company_id=1)
        target_company = _make_company(company_id=2)
        session = _make_session()

        def _get(model, pk):
            if model is CompanyAlias:
                return alias
            if model is Company:
                return target_company
            return None

        session.get.side_effect = _get
        with patch(_PATCH_AUDIT) as mock_audit:
            _client(session).patch("/api/v1/aliases/3/remap", json={"company_id": 2})
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["table_name"] == "company_alias"
        assert call_kwargs["action_type"] == "UPDATE"

    def test_404_alias_not_found(self) -> None:
        session = _make_session()
        session.get.return_value = None
        resp = _client(session).patch("/api/v1/aliases/999/remap", json={"company_id": 2})
        assert resp.status_code == 404

    def test_400_target_company_not_found(self) -> None:
        alias = _make_alias(alias_id=3, company_id=1)
        session = _make_session()

        call_count = 0

        def _get(model, pk):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return alias
            return None  # target company not found

        session.get.side_effect = _get
        with patch(_PATCH_AUDIT):
            resp = _client(session).patch("/api/v1/aliases/3/remap", json={"company_id": 99})
        assert resp.status_code == 400

    def test_403_no_write_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_READ_ONLY).patch(
            "/api/v1/aliases/3/remap", json={"company_id": 2}
        )
        assert resp.status_code == 403

    def test_403_no_permission(self) -> None:
        session = _make_session()
        resp = _client(session, user=_NO_PERM).patch(
            "/api/v1/aliases/3/remap", json={"company_id": 2}
        )
        assert resp.status_code == 403
