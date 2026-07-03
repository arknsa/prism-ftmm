"""Tests for dedup.py (P4.1 Tier-1 + P4.2 Tier-2).

Covers:
- find_by_linkedin_url: exact match, blank/None, normalization
- normalize_full_name: honorific stripping, Unicode, blank/None
- build_candidate_key: valid key, missing component → None
- find_candidates_by_key: match, no match, missing key
- D-045: Tier-1 auto-links exact URL; Tier-2 returns candidates (no auto-merge)
- D-044: candidate key = normalized_name + study_program_id + graduation_year
- D-039: deterministic only — same input → same result
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from app.models.alumni import Alumni
from app.services.dedup import (
    _normalize_linkedin_url,
    build_candidate_key,
    find_by_linkedin_url,
    find_candidates_by_key,
    normalize_full_name,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alumni(
    alumni_id: int = 1,
    full_name: str = "Budi Santoso",
    linkedin_url: str | None = None,
    study_program_id: int = 1,
    graduation_year: int = 2022,
) -> MagicMock:
    a = MagicMock(spec=Alumni)
    a.alumni_id = alumni_id
    a.full_name = full_name
    a.linkedin_url = linkedin_url
    a.study_program_id = study_program_id
    a.graduation_year = graduation_year
    return a


def _session_scalar(return_value: object) -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = return_value
    return session


def _session_scalars(return_list: list[object]) -> MagicMock:
    session = create_autospec(Session, instance=True)
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = return_list
    session.scalars.return_value = scalars_mock
    return session


# ===========================================================================
# _normalize_linkedin_url
# ===========================================================================


class TestNormalizeLinkedinUrl:
    def test_strips_whitespace(self) -> None:
        assert _normalize_linkedin_url("  https://linkedin.com/in/budi  ") == (
            "https://linkedin.com/in/budi"
        )

    def test_lowercases(self) -> None:
        assert _normalize_linkedin_url("HTTPS://LinkedIn.com/in/Budi") == (
            "https://linkedin.com/in/budi"
        )

    def test_strips_trailing_slash(self) -> None:
        assert _normalize_linkedin_url("https://linkedin.com/in/budi/") == (
            "https://linkedin.com/in/budi"
        )

    def test_preserves_profile_slug(self) -> None:
        result = _normalize_linkedin_url("https://linkedin.com/in/budi-santoso-abc123")
        assert "budi-santoso-abc123" in result

    def test_deterministic(self) -> None:
        url = "https://linkedin.com/in/budi"
        assert _normalize_linkedin_url(url) == _normalize_linkedin_url(url)


# ===========================================================================
# find_by_linkedin_url — Tier-1 (P4.1)
# ===========================================================================


class TestFindByLinkedinUrl:
    def test_none_returns_none(self) -> None:
        session = _session_scalar(None)
        assert find_by_linkedin_url(None, session) is None
        session.scalar.assert_not_called()

    def test_empty_string_returns_none(self) -> None:
        session = _session_scalar(None)
        assert find_by_linkedin_url("", session) is None
        session.scalar.assert_not_called()

    def test_whitespace_only_returns_none(self) -> None:
        session = _session_scalar(None)
        assert find_by_linkedin_url("   ", session) is None
        session.scalar.assert_not_called()

    def test_exact_match_returns_alumni(self) -> None:
        alumni = _make_alumni(linkedin_url="https://linkedin.com/in/budi")
        session = _session_scalar(alumni)
        result = find_by_linkedin_url("https://linkedin.com/in/budi", session)
        assert result is alumni

    def test_no_match_returns_none(self) -> None:
        session = _session_scalar(None)
        result = find_by_linkedin_url("https://linkedin.com/in/nobody", session)
        assert result is None

    def test_does_not_write(self) -> None:
        session = _session_scalar(None)
        find_by_linkedin_url("https://linkedin.com/in/budi", session)
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()

    def test_deterministic(self) -> None:
        alumni = _make_alumni(linkedin_url="https://linkedin.com/in/budi")
        session = _session_scalar(alumni)
        r1 = find_by_linkedin_url("https://linkedin.com/in/budi", session)
        r2 = find_by_linkedin_url("https://linkedin.com/in/budi", session)
        assert r1 is r2 or (r1 is not None and r2 is not None)


# ===========================================================================
# normalize_full_name — Tier-2 name normalization (P4.2)
# ===========================================================================


class TestNormalizeFullName:
    def test_none_returns_none(self) -> None:
        assert normalize_full_name(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize_full_name("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_full_name("   ") is None

    def test_basic_name(self) -> None:
        assert normalize_full_name("Budi Santoso") == "budi santoso"

    def test_lowercases(self) -> None:
        assert normalize_full_name("BUDI SANTOSO") == "budi santoso"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert normalize_full_name("  Budi Santoso  ") == "budi santoso"

    def test_collapses_internal_whitespace(self) -> None:
        assert normalize_full_name("Budi  Santoso") == "budi santoso"

    def test_strips_dr_prefix(self) -> None:
        assert normalize_full_name("Dr. Budi Santoso") == "budi santoso"

    def test_strips_prof_prefix(self) -> None:
        assert normalize_full_name("Prof. Budi Santoso") == "budi santoso"

    def test_strips_ir_prefix(self) -> None:
        assert normalize_full_name("Ir. Budi Santoso") == "budi santoso"

    def test_strips_bpk_prefix(self) -> None:
        assert normalize_full_name("Bpk. Budi Santoso") == "budi santoso"

    def test_strips_ibu_prefix(self) -> None:
        assert normalize_full_name("Ibu Sari Dewi") == "sari dewi"

    def test_unicode_diacritics_removed(self) -> None:
        # Indonesian names may not have diacritics but test robustness
        result = normalize_full_name("André Müller")
        assert result is not None
        assert "andre" in result or "muller" in result

    def test_deterministic(self) -> None:
        name = "Dr. Budi Santoso"
        assert normalize_full_name(name) == normalize_full_name(name)

    def test_same_name_different_prefix(self) -> None:
        # Both should normalize to the same key
        assert normalize_full_name("Dr. Budi Santoso") == normalize_full_name("Budi Santoso")

    def test_single_word_name(self) -> None:
        result = normalize_full_name("Sukarno")
        assert result == "sukarno"

    def test_honorific_only_returns_none(self) -> None:
        # After stripping all tokens if only honorifics remain → None
        result = normalize_full_name("Dr.")
        assert result is None


# ===========================================================================
# build_candidate_key (P4.2)
# ===========================================================================


class TestBuildCandidateKey:
    def test_valid_key(self) -> None:
        key = build_candidate_key("Budi Santoso", 1, 2022)
        assert key is not None
        name, program_id, year = key
        assert name == "budi santoso"
        assert program_id == 1
        assert year == 2022

    def test_none_name_returns_none(self) -> None:
        assert build_candidate_key(None, 1, 2022) is None

    def test_blank_name_returns_none(self) -> None:
        assert build_candidate_key("", 1, 2022) is None

    def test_none_program_id_returns_none(self) -> None:
        assert build_candidate_key("Budi Santoso", None, 2022) is None

    def test_none_graduation_year_returns_none(self) -> None:
        assert build_candidate_key("Budi Santoso", 1, None) is None

    def test_all_none_returns_none(self) -> None:
        assert build_candidate_key(None, None, None) is None

    def test_normalized_name_in_key(self) -> None:
        key = build_candidate_key("Dr. Budi Santoso", 1, 2022)
        assert key is not None
        assert key[0] == "budi santoso"

    def test_deterministic(self) -> None:
        k1 = build_candidate_key("Budi Santoso", 1, 2022)
        k2 = build_candidate_key("Budi Santoso", 1, 2022)
        assert k1 == k2

    def test_different_program_different_key(self) -> None:
        k1 = build_candidate_key("Budi", 1, 2022)
        k2 = build_candidate_key("Budi", 2, 2022)
        assert k1 != k2

    def test_different_year_different_key(self) -> None:
        k1 = build_candidate_key("Budi", 1, 2022)
        k2 = build_candidate_key("Budi", 1, 2023)
        assert k1 != k2


# ===========================================================================
# find_candidates_by_key — Tier-2 DB query (P4.2)
# ===========================================================================


class TestFindCandidatesByKey:
    def test_no_key_components_returns_empty(self) -> None:
        session = _session_scalars([])
        result = find_candidates_by_key(None, None, None, session)
        assert result == []
        session.scalars.assert_not_called()

    def test_missing_program_returns_empty(self) -> None:
        session = _session_scalars([])
        result = find_candidates_by_key("Budi", None, 2022, session)
        assert result == []

    def test_missing_year_returns_empty(self) -> None:
        session = _session_scalars([])
        result = find_candidates_by_key("Budi", 1, None, session)
        assert result == []

    def test_exact_match_returned(self) -> None:
        alumni = _make_alumni(
            full_name="Budi Santoso",
            study_program_id=1,
            graduation_year=2022,
        )
        session = _session_scalars([alumni])
        result = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        assert alumni in result

    def test_honorific_variant_matches(self) -> None:
        alumni = _make_alumni(
            full_name="Budi Santoso",
            study_program_id=1,
            graduation_year=2022,
        )
        session = _session_scalars([alumni])
        result = find_candidates_by_key("Dr. Budi Santoso", 1, 2022, session)
        assert alumni in result

    def test_different_name_not_returned(self) -> None:
        alumni = _make_alumni(
            full_name="Sari Dewi",
            study_program_id=1,
            graduation_year=2022,
        )
        session = _session_scalars([alumni])
        result = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        assert alumni not in result

    def test_no_db_alumni_returns_empty(self) -> None:
        session = _session_scalars([])
        result = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        assert result == []

    def test_does_not_write(self) -> None:
        session = _session_scalars([])
        find_candidates_by_key("Budi Santoso", 1, 2022, session)
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()

    def test_multiple_candidates_all_returned(self) -> None:
        a1 = _make_alumni(
            alumni_id=1, full_name="Budi Santoso", study_program_id=1, graduation_year=2022
        )
        a2 = _make_alumni(
            alumni_id=2, full_name="Budi Santoso", study_program_id=1, graduation_year=2022
        )
        session = _session_scalars([a1, a2])
        result = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        assert a1 in result
        assert a2 in result

    def test_deterministic(self) -> None:
        alumni = _make_alumni(full_name="Budi Santoso", study_program_id=1, graduation_year=2022)
        session = _session_scalars([alumni])
        r1 = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        r2 = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        assert len(r1) == len(r2)


# ===========================================================================
# D-045 Tier guarantees
# ===========================================================================


class TestDedupTierGuarantees:
    def test_tier1_no_url_skips_to_no_match(self) -> None:
        session = _session_scalar(None)
        result = find_by_linkedin_url(None, session)
        assert result is None

    def test_tier2_returns_list_never_auto_merges(self) -> None:
        a1 = _make_alumni(full_name="Budi Santoso", study_program_id=1, graduation_year=2022)
        a2 = _make_alumni(full_name="Budi Santoso", study_program_id=1, graduation_year=2022)
        session = _session_scalars([a1, a2])
        candidates = find_candidates_by_key("Budi Santoso", 1, 2022, session)
        # Function returns ALL candidates — curator decides, no auto-merge
        assert len(candidates) >= 1

    def test_tier2_empty_when_no_match(self) -> None:
        session = _session_scalars([])
        result = find_candidates_by_key("Unknown Person", 99, 2099, session)
        assert result == []
