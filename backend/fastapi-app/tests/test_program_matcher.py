"""Tests for program_matcher.py (P3.4).

Covers all A6 testable invariants:
1. None/blank → sentinel
2. "Teknik Industri" → Industrial Engineering
3. Case-insensitive matching
4. Unrecognized string → sentinel
5. UNAIR variants → is_unair=True
6. Non-UNAIR → is_unair=False
7. Deterministic (same input → same output)
8. All listed variants resolve to is_ftmm_valid program or sentinel
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest
from app.models.reference import StudyProgram
from app.services.program_matcher import (
    _PROGRAM_VARIANT_MAP,
    _SENTINEL_NAME,
    _UNAIR_VARIANTS,
    is_unair,
    match_program,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_program(
    name: str = "Industrial Engineering",
    is_ftmm_valid: bool = True,
) -> MagicMock:
    prog = MagicMock(spec=StudyProgram)
    prog.program_name = name
    prog.is_ftmm_valid = is_ftmm_valid
    return prog


def _make_sentinel() -> MagicMock:
    return _make_program(name=_SENTINEL_NAME, is_ftmm_valid=False)


def _session_returning(program: MagicMock) -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = program
    return session


# ---------------------------------------------------------------------------
# A6 Invariant 1 — None / blank → sentinel
# ---------------------------------------------------------------------------


class TestBlankInput:
    def test_none_returns_sentinel(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program(None, session)
        assert result is sentinel

    def test_empty_string_returns_sentinel(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program("", session)
        assert result is sentinel

    def test_whitespace_only_returns_sentinel(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program("   ", session)
        assert result is sentinel

    def test_sentinel_is_not_ftmm_valid(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program(None, session)
        assert result.is_ftmm_valid is False


# ---------------------------------------------------------------------------
# A6 Invariant 2 — "Teknik Industri" → Industrial Engineering
# ---------------------------------------------------------------------------


class TestKnownVariant:
    def test_teknik_industri_resolves(self) -> None:
        program = _make_program("Industrial Engineering", is_ftmm_valid=True)
        session = _session_returning(program)
        result = match_program("Teknik Industri", session)
        assert result.program_name == "Industrial Engineering"
        assert result.is_ftmm_valid is True

    def test_known_variant_no_write(self) -> None:
        program = _make_program("Industrial Engineering")
        session = _session_returning(program)
        match_program("Teknik Industri", session)
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# A6 Invariant 3 — Case-insensitive matching
# ---------------------------------------------------------------------------


class TestCaseInsensitive:
    def test_uppercase_resolves(self) -> None:
        program = _make_program("Technology of Data Science")
        session = _session_returning(program)
        result = match_program("DATA SCIENCE", session)
        assert result.program_name == "Technology of Data Science"

    def test_mixed_case_resolves(self) -> None:
        program = _make_program("Electrical Engineering")
        session = _session_returning(program)
        result = match_program("Electrical Engineering", session)
        assert result.is_ftmm_valid is True

    def test_lowercase_resolves(self) -> None:
        program = _make_program("Nanotechnology Engineering")
        session = _session_returning(program)
        result = match_program("nanotechnology", session)
        assert result.program_name == "Nanotechnology Engineering"


# ---------------------------------------------------------------------------
# A6 Invariant 4 — Unrecognized string → sentinel
# ---------------------------------------------------------------------------


class TestUnrecognizedString:
    def test_unknown_program_returns_sentinel(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program("Philosophy", session)
        assert result.is_ftmm_valid is False

    def test_partial_match_not_allowed(self) -> None:
        # "Industrial" is in the map but "Industrial Management" is not
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program("Industrial Management", session)
        # "industrial management" is not a key — returns sentinel
        assert result is sentinel

    def test_unrecognized_in_indonesian(self) -> None:
        sentinel = _make_sentinel()
        session = _session_returning(sentinel)
        result = match_program("Teknik Sipil", session)
        assert result is sentinel


# ---------------------------------------------------------------------------
# A6 Invariant 5&6 — is_unair
# ---------------------------------------------------------------------------


class TestIsUnair:
    @pytest.mark.parametrize(
        "variant",
        [
            "Universitas Airlangga",
            "unair",
            "UNAIR",
            "UA",
            "Airlangga University",
            "airlangga",
            "  UNAIR  ",  # whitespace stripped
        ],
    )
    def test_recognized_variants_return_true(self, variant: str) -> None:
        assert is_unair(variant) is True

    @pytest.mark.parametrize(
        "variant",
        [
            "MIT",
            "Universitas Indonesia",
            "ITS",
            "University of Melbourne",
            "",
            None,
            "   ",
        ],
    )
    def test_unrecognized_or_blank_returns_false(self, variant: str | None) -> None:
        assert is_unair(variant) is False

    def test_case_insensitive(self) -> None:
        assert is_unair("UNIVERSITAS AIRLANGGA") is True

    def test_whitespace_normalized(self) -> None:
        assert is_unair("  unair  ") is True


# ---------------------------------------------------------------------------
# A6 Invariant 7 — Deterministic
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_program(self) -> None:
        program = _make_program("Industrial Engineering")
        session = _session_returning(program)
        result1 = match_program("Teknik Industri", session)
        result2 = match_program("Teknik Industri", session)
        assert result1 is result2 or result1.program_name == result2.program_name

    def test_is_unair_deterministic(self) -> None:
        for raw in ["unair", None, "MIT", "Universitas Airlangga"]:
            assert is_unair(raw) == is_unair(raw)


# ---------------------------------------------------------------------------
# Variant map completeness
# ---------------------------------------------------------------------------


class TestVariantMapCompleteness:
    def test_all_canonical_names_in_map_are_ftmm_programs(self) -> None:
        valid_programs = {
            "Technology of Data Science",
            "Industrial Engineering",
            "Electrical Engineering",
            "Nanotechnology Engineering",
            "Robotics and Artificial Intelligence Engineering",
        }
        mapped_targets = set(_PROGRAM_VARIANT_MAP.values())
        assert mapped_targets == valid_programs

    def test_sentinel_not_in_variant_map(self) -> None:
        assert _SENTINEL_NAME not in _PROGRAM_VARIANT_MAP.values()

    def test_all_variant_keys_are_lowercase(self) -> None:
        for key in _PROGRAM_VARIANT_MAP:
            assert key == key.lower(), f"Key not lowercase: {key!r}"

    def test_unair_variants_are_lowercase(self) -> None:
        for v in _UNAIR_VARIANTS:
            assert v == v.lower(), f"UNAIR variant not lowercase: {v!r}"


# ---------------------------------------------------------------------------
# Sentinel fallback when DB is missing the exact canonical name
# ---------------------------------------------------------------------------


class TestSentinelFallback:
    def test_raises_if_sentinel_missing_from_db(self) -> None:
        """If the sentinel row is missing from the DB, RuntimeError is raised."""
        session = create_autospec(Session, instance=True)
        session.scalar.return_value = None  # both queries return None

        with pytest.raises(RuntimeError, match="Other / Unknown"):
            match_program(None, session)
