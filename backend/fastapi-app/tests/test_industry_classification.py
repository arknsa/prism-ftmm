"""Tests for industry_classification.py (P3.7)."""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from app.models.company import Company
from app.models.reference import Industry
from app.services.industry_classification import attach_industry
from sqlalchemy.orm import Session


def _make_company(industry_id: int | None = None) -> MagicMock:
    company = MagicMock(spec=Company)
    company.industry_id = industry_id
    return company


def _make_industry(industry_id: int = 5, name: str = "Software Development") -> MagicMock:
    ind = MagicMock(spec=Industry)
    ind.industry_id = industry_id
    ind.industry_name = name
    return ind


class TestAttachIndustryBlankOrAbsent:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.company = _make_company()

    def test_none_raw_industry_no_op(self) -> None:
        attach_industry(self.company, None, self.session)
        self.session.scalar.assert_not_called()

    def test_empty_string_no_op(self) -> None:
        attach_industry(self.company, "", self.session)
        self.session.scalar.assert_not_called()

    def test_whitespace_only_no_op(self) -> None:
        attach_industry(self.company, "   ", self.session)
        self.session.scalar.assert_not_called()

    def test_industry_id_unchanged_on_blank(self) -> None:
        self.company.industry_id = None
        attach_industry(self.company, "", self.session)
        assert self.company.industry_id is None


class TestAttachIndustryAlreadyClassified:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.company = _make_company(industry_id=3)

    def test_does_not_overwrite_existing_classification(self) -> None:
        attach_industry(self.company, "Software Development", self.session)
        # industry_id must remain 3 — not overwritten
        assert self.company.industry_id == 3

    def test_no_db_lookup_when_already_set(self) -> None:
        attach_industry(self.company, "Software Development", self.session)
        self.session.scalar.assert_not_called()


class TestAttachIndustryExactMatch:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.company = _make_company()
        self.industry = _make_industry(industry_id=7)

    def test_sets_industry_id_on_match(self) -> None:
        self.session.scalar.return_value = self.industry
        attach_industry(self.company, "Software Development", self.session)
        assert self.company.industry_id == 7

    def test_strips_whitespace_before_lookup(self) -> None:
        self.session.scalar.return_value = self.industry
        attach_industry(self.company, "  Software Development  ", self.session)
        assert self.company.industry_id == 7

    def test_one_db_call(self) -> None:
        self.session.scalar.return_value = self.industry
        attach_industry(self.company, "Software Development", self.session)
        self.session.scalar.assert_called_once()

    def test_no_add_no_flush(self) -> None:
        self.session.scalar.return_value = self.industry
        attach_industry(self.company, "Software Development", self.session)
        self.session.add.assert_not_called()
        self.session.flush.assert_not_called()


class TestAttachIndustryNoMatch:
    def setup_method(self) -> None:
        self.session = create_autospec(Session, instance=True)
        self.session.scalar.return_value = None
        self.company = _make_company()

    def test_industry_id_stays_none_on_no_match(self) -> None:
        attach_industry(self.company, "Unknown Sector XYZ", self.session)
        assert self.company.industry_id is None

    def test_no_new_industry_created(self) -> None:
        attach_industry(self.company, "Unknown Sector XYZ", self.session)
        self.session.add.assert_not_called()

    def test_does_not_match_case_insensitively(self) -> None:
        # Match is exact — "software development" ≠ "Software Development"
        self.session.scalar.return_value = None
        attach_industry(self.company, "software development", self.session)
        assert self.company.industry_id is None
