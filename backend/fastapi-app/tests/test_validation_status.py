"""Tests for validation_status.py (P3.5).

Covers all Artifact A6 §5 validation-status assignment rules:
- valid program + UNAIR → pending
- valid program + non-UNAIR → pending
- sentinel + UNAIR → pending
- sentinel + non-UNAIR → rejected
- never returns "validated" (curator gate)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.models.reference import StudyProgram
from app.services.validation_status import (
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_VALIDATED,
    assign_validation_status,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_program() -> MagicMock:
    prog = MagicMock(spec=StudyProgram)
    prog.is_ftmm_valid = True
    prog.program_name = "Industrial Engineering"
    return prog


def _sentinel_program() -> MagicMock:
    prog = MagicMock(spec=StudyProgram)
    prog.is_ftmm_valid = False
    prog.program_name = "Other / Unknown"
    return prog


# ---------------------------------------------------------------------------
# A6 §5 — Four assignment rules
# ---------------------------------------------------------------------------


class TestAssignmentRules:
    def test_valid_program_unair_is_pending(self) -> None:
        """Valid program + UNAIR → pending (NOT auto-validated, D-024)."""
        result = assign_validation_status(_valid_program(), university_matched=True)
        assert result == STATUS_PENDING

    def test_valid_program_non_unair_is_pending(self) -> None:
        """Valid program + non-UNAIR → pending (curator reviews — may be transfer)."""
        result = assign_validation_status(_valid_program(), university_matched=False)
        assert result == STATUS_PENDING

    def test_sentinel_unair_is_pending(self) -> None:
        """Sentinel + UNAIR → pending (UNAIR student, unknown program)."""
        result = assign_validation_status(_sentinel_program(), university_matched=True)
        assert result == STATUS_PENDING

    def test_sentinel_non_unair_is_rejected(self) -> None:
        """Sentinel + non-UNAIR → rejected (neither program nor university matches)."""
        result = assign_validation_status(_sentinel_program(), university_matched=False)
        assert result == STATUS_REJECTED


# ---------------------------------------------------------------------------
# D-024 — Never auto-validates
# ---------------------------------------------------------------------------


class TestNeverAutoValidates:
    def test_never_returns_validated(self) -> None:
        """The pipeline never produces 'validated' — that is curator-only (D-024)."""
        combinations = [
            (_valid_program(), True),
            (_valid_program(), False),
            (_sentinel_program(), True),
            (_sentinel_program(), False),
        ]
        for program, univ in combinations:
            result = assign_validation_status(program, univ)
            assert result != STATUS_VALIDATED, (
                f"assign_validation_status returned 'validated' for "
                f"is_ftmm_valid={program.is_ftmm_valid}, university_matched={univ}"
            )

    def test_validated_constant_value(self) -> None:
        assert STATUS_VALIDATED == "validated"


# ---------------------------------------------------------------------------
# D-047 — Nothing silently dropped
# ---------------------------------------------------------------------------


class TestNothingSilentlyDropped:
    @pytest.mark.parametrize(
        "program_valid,univ_matched",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_always_returns_a_status(self, program_valid: bool, univ_matched: bool) -> None:
        prog = _valid_program() if program_valid else _sentinel_program()
        result = assign_validation_status(prog, univ_matched)
        assert result in (STATUS_PENDING, STATUS_REJECTED)
        assert result is not None
        assert result != ""


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_same_output(self) -> None:
        prog = _valid_program()
        for univ in [True, False]:
            r1 = assign_validation_status(prog, univ)
            r2 = assign_validation_status(prog, univ)
            assert r1 == r2

    def test_rejected_only_when_both_fail(self) -> None:
        """Rejection requires BOTH program non-valid AND university non-matching."""
        # Only this combination → rejected
        assert assign_validation_status(_sentinel_program(), False) == STATUS_REJECTED
        # All other combos → pending
        assert assign_validation_status(_sentinel_program(), True) == STATUS_PENDING
        assert assign_validation_status(_valid_program(), True) == STATUS_PENDING
        assert assign_validation_status(_valid_program(), False) == STATUS_PENDING


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------


class TestStatusConstants:
    def test_pending_value(self) -> None:
        assert STATUS_PENDING == "pending"

    def test_rejected_value(self) -> None:
        assert STATUS_REJECTED == "rejected"

    def test_validated_value(self) -> None:
        assert STATUS_VALIDATED == "validated"
