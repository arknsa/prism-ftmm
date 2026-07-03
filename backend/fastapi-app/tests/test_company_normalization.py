"""Tests for company_normalization.py (P3.6)."""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from app.models.company import Company, CompanyAlias
from app.services.company_normalization import _normalize_alias, resolve_company
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# _normalize_alias unit tests
# ---------------------------------------------------------------------------


class TestNormalizeAlias:
    def test_strips_leading_trailing_whitespace(self) -> None:
        assert _normalize_alias("  Acme Corp  ") == "Acme Corp"

    def test_collapses_internal_whitespace(self) -> None:
        assert _normalize_alias("Acme  Corp   Ltd") == "Acme Corp Ltd"

    def test_preserves_casing(self) -> None:
        assert _normalize_alias("McKinsey & Company") == "McKinsey & Company"

    def test_empty_string_after_strip(self) -> None:
        # blank input → empty string (caller checks for blank before calling)
        assert _normalize_alias("   ") == ""

    def test_tab_collapsed(self) -> None:
        assert _normalize_alias("Acme\tCorp") == "Acme Corp"

    def test_mixed_whitespace(self) -> None:
        assert _normalize_alias("Acme \t Corp") == "Acme Corp"


# ---------------------------------------------------------------------------
# resolve_company — blank/absent input
# ---------------------------------------------------------------------------


class TestResolveCompanyBlank:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)

    def test_none_returns_none(self) -> None:
        assert resolve_company(None, source_id=1, session=self.session) is None

    def test_empty_string_returns_none(self) -> None:
        assert resolve_company("", source_id=1, session=self.session) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert resolve_company("   ", source_id=1, session=self.session) is None

    def test_no_db_calls_on_blank(self) -> None:
        resolve_company(None, source_id=1, session=self.session)
        self.session.scalar.assert_not_called()
        self.session.add.assert_not_called()
        self.session.flush.assert_not_called()


# ---------------------------------------------------------------------------
# resolve_company — existing alias found
# ---------------------------------------------------------------------------


class TestResolveCompanyExistingAlias:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.existing_company = MagicMock(spec=Company)
        self.existing_company.company_id = 7
        self.existing_alias = MagicMock(spec=CompanyAlias)
        self.existing_alias.company_id = 7

    def test_returns_existing_company(self) -> None:
        self.session.scalar.return_value = self.existing_alias
        self.session.get.return_value = self.existing_company

        result = resolve_company("  Acme Corp  ", source_id=2, session=self.session)

        assert result is self.existing_company

    def test_no_new_objects_added(self) -> None:
        self.session.scalar.return_value = self.existing_alias
        self.session.get.return_value = self.existing_company

        resolve_company("Acme Corp", source_id=2, session=self.session)

        self.session.add.assert_not_called()
        self.session.flush.assert_not_called()

    def test_alias_lookup_uses_normalized_name(self) -> None:
        self.session.scalar.return_value = self.existing_alias
        self.session.get.return_value = self.existing_company

        resolve_company("  Acme  Corp  ", source_id=2, session=self.session)

        # The scalar call should pass a query (we just check it was called once)
        self.session.scalar.assert_called_once()

    def test_company_fetched_by_id(self) -> None:
        self.session.scalar.return_value = self.existing_alias
        self.session.get.return_value = self.existing_company

        resolve_company("Acme Corp", source_id=2, session=self.session)

        self.session.get.assert_called_once_with(Company, 7)


# ---------------------------------------------------------------------------
# resolve_company — first sight (new company + alias)
# ---------------------------------------------------------------------------


class TestResolveCompanyFirstSight:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        # No alias found
        self.session.scalar.return_value = None
        # flush sets company_id on added objects
        self.session.flush = MagicMock()

    def test_returns_company_instance(self) -> None:
        result = resolve_company("New Corp", source_id=3, session=self.session)
        assert isinstance(result, Company)

    def test_canonical_name_normalized(self) -> None:
        result = resolve_company("  New  Corp  ", source_id=3, session=self.session)
        assert isinstance(result, Company)
        assert result.canonical_name == "New Corp"

    def test_industry_id_none_on_creation(self) -> None:
        result = resolve_company("New Corp", source_id=3, session=self.session)
        assert isinstance(result, Company)
        assert result.industry_id is None

    def test_location_id_none_on_creation(self) -> None:
        result = resolve_company("New Corp", source_id=3, session=self.session)
        assert isinstance(result, Company)
        assert result.location_id is None

    def test_flush_called_before_alias(self) -> None:
        flush_calls: list[str] = []
        add_calls: list[str] = []

        def mock_flush() -> None:
            flush_calls.append("flush")

        def mock_add(obj: object) -> None:
            add_calls.append(type(obj).__name__ + f"@flush_count={len(flush_calls)}")

        self.session.flush = mock_flush
        self.session.add = mock_add

        resolve_company("New Corp", source_id=3, session=self.session)

        # Company added first (flush_count=0), then flush, then CompanyAlias added (flush_count=1)
        assert add_calls[0].startswith("Company@flush_count=0")
        assert add_calls[1].startswith("CompanyAlias@flush_count=1")

    def test_alias_source_id_set(self) -> None:
        added: list[object] = []
        self.session.add = lambda obj: added.append(obj)

        resolve_company("New Corp", source_id=42, session=self.session)

        aliases = [obj for obj in added if isinstance(obj, CompanyAlias)]
        assert len(aliases) == 1
        assert aliases[0].source_id == 42

    def test_alias_name_matches_normalized(self) -> None:
        added: list[object] = []
        self.session.add = lambda obj: added.append(obj)

        resolve_company("  New  Corp  ", source_id=1, session=self.session)

        aliases = [obj for obj in added if isinstance(obj, CompanyAlias)]
        assert aliases[0].alias_name == "New Corp"

    def test_exactly_two_objects_added(self) -> None:
        added: list[object] = []
        self.session.add = lambda obj: added.append(obj)

        resolve_company("New Corp", source_id=1, session=self.session)

        assert len(added) == 2
        types = {type(obj).__name__ for obj in added}
        assert types == {"Company", "CompanyAlias"}

    def test_deterministic_same_input_same_normalized_name(self) -> None:
        result1 = resolve_company("Acme Corp", source_id=1, session=self.session)
        # Reset mocks and call again
        self.session.scalar.return_value = None
        result2 = resolve_company("Acme Corp", source_id=1, session=self.session)
        assert isinstance(result1, Company)
        assert isinstance(result2, Company)
        assert result1.canonical_name == result2.canonical_name


# ---------------------------------------------------------------------------
# resolve_company — source_id=None (CLI context)
# ---------------------------------------------------------------------------


class TestResolveCompanyCliContext:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.session.scalar.return_value = None
        self.session.flush = MagicMock()

    def test_source_id_none_allowed(self) -> None:
        result = resolve_company("Some Corp", source_id=None, session=self.session)
        assert isinstance(result, Company)

    def test_alias_source_id_none_when_cli(self) -> None:
        added: list[object] = []
        self.session.add = lambda obj: added.append(obj)

        resolve_company("Some Corp", source_id=None, session=self.session)

        aliases = [obj for obj in added if isinstance(obj, CompanyAlias)]
        assert aliases[0].source_id is None
