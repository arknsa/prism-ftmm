"""Tests for role_seniority.py (P3.9).

Covers:
- clean_role_title: Artifact A5 cleaning invariants
- classify_seniority: all 10 Artifact A4 testable invariants + priority ordering
"""

from __future__ import annotations

import pytest
from app.services.role_seniority import SENIORITY_LEVELS, classify_seniority, clean_role_title

# ---------------------------------------------------------------------------
# clean_role_title (Artifact A5)
# ---------------------------------------------------------------------------


class TestCleanRoleTitle:
    def test_none_returns_none(self) -> None:
        assert clean_role_title(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert clean_role_title("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert clean_role_title("   ") is None

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert clean_role_title("  Software Engineer  ") == "Software Engineer"

    def test_collapses_internal_whitespace(self) -> None:
        assert clean_role_title("Data  Scientist") == "Data Scientist"

    def test_preserves_casing(self) -> None:
        assert clean_role_title("CTO") == "CTO"

    def test_preserves_mixed_casing(self) -> None:
        assert clean_role_title("Senior Software Engineer") == "Senior Software Engineer"

    def test_tab_collapsed(self) -> None:
        assert clean_role_title("Software\tEngineer") == "Software Engineer"

    def test_mixed_whitespace_collapsed(self) -> None:
        assert clean_role_title("Data \t Scientist") == "Data Scientist"

    def test_single_word_preserved(self) -> None:
        assert clean_role_title("Manager") == "Manager"

    def test_deterministic_same_input(self) -> None:
        raw = "  Senior  Developer  "
        assert clean_role_title(raw) == clean_role_title(raw)


# ---------------------------------------------------------------------------
# classify_seniority — blank/None input
# ---------------------------------------------------------------------------


class TestClassifySeniorityBlank:
    def test_none_returns_other(self) -> None:
        assert classify_seniority(None) == "Other"

    def test_empty_string_returns_other(self) -> None:
        assert classify_seniority("") == "Other"

    def test_whitespace_only_returns_other(self) -> None:
        assert classify_seniority("   ") == "Other"


# ---------------------------------------------------------------------------
# A4 Testable Invariants (§4)
# ---------------------------------------------------------------------------


class TestA4Invariants:
    def test_invariant_2_software_engineer_is_mid(self) -> None:
        assert classify_seniority("Software Engineer") == "Mid"

    def test_invariant_3_senior_software_engineer_is_senior(self) -> None:
        assert classify_seniority("Senior Software Engineer") == "Senior"

    def test_invariant_4_junior_data_analyst_is_entry(self) -> None:
        assert classify_seniority("Junior Data Analyst") == "Entry"

    def test_invariant_5_magang_is_intern(self) -> None:
        assert classify_seniority("Magang") == "Intern"

    def test_invariant_6_cto_is_executive(self) -> None:
        assert classify_seniority("CTO") == "Executive"

    def test_invariant_7_engineering_manager_is_manager(self) -> None:
        assert classify_seniority("Engineering Manager") == "Manager"

    def test_invariant_8_tech_lead_is_lead(self) -> None:
        assert classify_seniority("Tech Lead") == "Lead"

    def test_invariant_9_vp_engineering_is_director(self) -> None:
        assert classify_seniority("Vice President of Engineering") == "Director"

    def test_invariant_10_freelance_photographer_is_other(self) -> None:
        assert classify_seniority("Freelance Photographer") == "Other"

    def test_invariant_11_deterministic(self) -> None:
        for title in ["Software Engineer", "CTO", "Magang", "Director of Product", None]:
            result1 = classify_seniority(title)
            result2 = classify_seniority(title)
            assert result1 == result2


# ---------------------------------------------------------------------------
# Priority ordering tests
# ---------------------------------------------------------------------------


class TestSeniorityPriority:
    def test_executive_beats_manager(self) -> None:
        # "CEO" → Executive (rule 1), not Manager
        assert classify_seniority("CEO") == "Executive"

    def test_director_beats_manager(self) -> None:
        # "Director of Engineering" → Director (rule 2), not Manager
        assert classify_seniority("Director of Engineering") == "Director"

    def test_manager_beats_lead(self) -> None:
        # "Team Lead Manager" → Manager (rule 3 fires before Lead)
        # "manager" appears → Manager wins
        assert classify_seniority("Team Lead Manager") == "Manager"

    def test_senior_beats_mid(self) -> None:
        # "Senior Engineer" → Senior (rule 5), not Mid (rule 8)
        assert classify_seniority("Senior Engineer") == "Senior"

    def test_intern_beats_entry(self) -> None:
        # "Intern Analyst" → Intern (rule 6), not Entry (rule 7)
        assert classify_seniority("Intern Analyst") == "Intern"

    def test_entry_beats_mid(self) -> None:
        # "Junior Software Engineer" → Entry (rule 7 "junior"), not Mid (rule 8 "engineer")
        assert classify_seniority("Junior Software Engineer") == "Entry"

    def test_lead_beats_senior(self) -> None:
        # "Senior Tech Lead" — Lead (rule 4) beats Senior (rule 5)
        # "tech lead" is in rule 4 which fires before rule 5
        assert classify_seniority("Senior Tech Lead") == "Lead"


# ---------------------------------------------------------------------------
# Executive level
# ---------------------------------------------------------------------------


class TestExecutiveLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Chief Executive Officer",
            "CTO",
            "CFO",
            "COO",
            "CPO",
            "Chief Technology Officer",
            "Founder",
            "Co-Founder",
            "President",
        ],
    )
    def test_executive_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Executive"


# ---------------------------------------------------------------------------
# Director level
# ---------------------------------------------------------------------------


class TestDirectorLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Director of Product",
            "VP of Engineering",
            "SVP Sales",
            "EVP Operations",
            "Head of Data",
            "Vice President",
        ],
    )
    def test_director_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Director"


# ---------------------------------------------------------------------------
# Manager level
# ---------------------------------------------------------------------------


class TestManagerLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Product Manager",
            "Engineering Manager",
            "Project Supervisor",
            "Kepala Bagian",
            "Area Superintendent",
        ],
    )
    def test_manager_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Manager"


# ---------------------------------------------------------------------------
# Lead level
# ---------------------------------------------------------------------------


class TestLeadLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Tech Lead",
            "Team Lead",
            "Squad Lead",
            "Chapter Lead",
            "Tribe Lead",
            "Backend Lead",
        ],
    )
    def test_lead_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Lead"


# ---------------------------------------------------------------------------
# Senior level
# ---------------------------------------------------------------------------


class TestSeniorLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Senior Software Engineer",
            "Sr. Developer",
            "Principal Architect",
            "Data Science Specialist",
            "Domain Expert",
            "Solutions Architect",
            "Senior Consultant",
        ],
    )
    def test_senior_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Senior"


# ---------------------------------------------------------------------------
# Intern level
# ---------------------------------------------------------------------------


class TestInternLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineering Intern",
            "Magang",
            "Trainee",
            "Apprentice Developer",
            "Practicum",
            "Kerja Praktek",
        ],
    )
    def test_intern_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Intern"


# ---------------------------------------------------------------------------
# Entry level
# ---------------------------------------------------------------------------


class TestEntryLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Junior Software Engineer",
            "Jr. Developer",
            "Associate Engineer",
            "Staff Engineer",
            "Business Analyst",
            "Graduate Engineer",
            "Fresh Graduate",
            "Entry Level Developer",
        ],
    )
    def test_entry_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Entry"


# ---------------------------------------------------------------------------
# Mid level
# ---------------------------------------------------------------------------


class TestMidLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineer",
            "Data Scientist",
            "Frontend Developer",
            "UI Designer",
            "Research Engineer",
            "Mid-level Developer",
        ],
    )
    def test_mid_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Mid"


# ---------------------------------------------------------------------------
# Other level
# ---------------------------------------------------------------------------


class TestOtherLevel:
    @pytest.mark.parametrize(
        "title",
        [
            "Freelance Photographer",
            "Sales Representative",
            "Barista",
            "Content Creator",
            "Wirausahawan",
        ],
    )
    def test_other_titles(self, title: str) -> None:
        assert classify_seniority(title) == "Other"


# ---------------------------------------------------------------------------
# SENIORITY_LEVELS constant completeness
# ---------------------------------------------------------------------------


class TestSeniorityLevelsConstant:
    def test_all_levels_present(self) -> None:
        expected = {
            "Executive",
            "Director",
            "Manager",
            "Lead",
            "Senior",
            "Intern",
            "Entry",
            "Mid",
            "Other",
        }
        assert set(SENIORITY_LEVELS) == expected

    def test_other_is_last(self) -> None:
        assert SENIORITY_LEVELS[-1] == "Other"
