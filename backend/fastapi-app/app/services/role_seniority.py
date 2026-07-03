"""Role cleaning and seniority classification service (P3.9).

Implements two deterministic operations per Artifact A4 (SENIORITY_LADDER_SPEC.md)
and Artifact A5 (ROLE_NORMALIZATION_SPEC.md):

  clean_role_title(raw)   → str | None  (light whitespace cleaning only, A5)
  classify_seniority(raw) → str         (keyword-based ladder, A4)

Design constraints (D-020, D-039, D-002):
- Deterministic only: same input → same output every call.
- No fuzzy matching, no ML, no inference.
- Role title stored verbatim after light cleaning (A5).
- Seniority assigned from a priority-ordered keyword table (A4).
- Unclassifiable roles → "Other" (never NULL, never dropped).
- These are pure functions: no session, no DB access, no side effects.

Decisions: D-020, D-002, D-039, Artifact A4, Artifact A5.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Seniority ladder (A4 §2)
# ---------------------------------------------------------------------------

SENIORITY_LEVELS: tuple[str, ...] = (
    "Executive",
    "Director",
    "Manager",
    "Lead",
    "Senior",
    "Intern",
    "Entry",
    "Mid",
    "Other",
)

# Priority-ordered rules: (level, substr_tokens, pattern).
# First matching rule wins (A4 §3, "first-match wins").
# substr_tokens: checked as plain substrings (safe for long phrases/full words).
# pattern: optional compiled regex for tokens needing word-boundary or lookbehind guards.
_SENIORITY_RULES: tuple[tuple[str, frozenset[str], re.Pattern[str] | None], ...] = (
    (
        "Executive",
        frozenset({"chief", "founder", "co-founder", "cofounder"}),
        # "president" alone (not "vice president"); C-suite acronyms need word boundaries.
        re.compile(r"\b(?:ceo|cto|cfo|coo|cpo|cxo)\b|(?<!vice )(?<!\bexecutive )\bpresident\b"),
    ),
    (
        "Director",
        frozenset({"director", "vice president", "head of", "head, "}),
        re.compile(r"\b(?:vp|svp|evp)\b"),
    ),
    (
        "Manager",
        frozenset({"manager", "supervisor", "superintendent", "kepala"}),
        None,
    ),
    (
        "Lead",
        frozenset(
            {
                "team lead",
                "tech lead",
                "squad lead",
                "chapter lead",
                "tribe lead",
                " lead",
                "lead ",
            }
        ),
        None,
    ),
    (
        "Senior",
        frozenset(
            {
                "senior",
                "sr.",
                "sr ",
                "principal",
                "specialist",
                "expert",
                "architect",
                "consultant",
            }
        ),
        None,
    ),
    (
        "Intern",
        frozenset({"intern", "magang", "trainee", "apprentice", "practicum", "praktek"}),
        None,
    ),
    (
        "Entry",
        frozenset(
            {
                "junior",
                "jr.",
                "jr ",
                "associate",
                "staff",
                "analyst",
                "graduate",
                "fresh",
                "entry",
            }
        ),
        None,
    ),
    (
        "Mid",
        frozenset({"engineer", "developer", "scientist", "designer", "researcher", "mid"}),
        None,
    ),
)

# Roman numeral tokens that need word-boundary guarding (A4 §3 note)
_ROMAN_TOKENS: frozenset[str] = frozenset({"ii", "iii", "iv"})
_ROMAN_PATTERN = re.compile(r"\b(ii|iii|iv)\b")


def _normalize(raw: str) -> str:
    """Lowercase and collapse whitespace for deterministic matching."""
    return re.sub(r"\s+", " ", raw.strip().lower())


def clean_role_title(raw_role_title: str | None) -> str | None:
    """Apply light deterministic cleaning to a raw role title (Artifact A5).

    Steps:
    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace runs to a single space.
    3. Preserve original casing.
    4. Blank/None → None.

    Returns the cleaned string or None. Does NOT remap or canonicalize.
    """
    if not raw_role_title:
        return None
    cleaned = re.sub(r"\s+", " ", raw_role_title.strip())
    return cleaned if cleaned else None


def classify_seniority(raw_role_title: str | None) -> str:
    """Map a raw role title to a seniority level (Artifact A4).

    Algorithm (A4 §3, priority order):
    1. Normalize: lowercase + collapse whitespace.
    2. Apply rules in priority order; first matching rule wins.
    3. Check roman numeral tokens ("ii", "iii", "iv") with word-boundary guard
       before the Mid-level rule (last before "Other").
    4. Default: "Other".

    Args:
        raw_role_title: raw role string from staged row (may be None/blank).

    Returns:
        One of the canonical seniority level strings from SENIORITY_LEVELS.
        Never returns None or raises.
    """
    if not raw_role_title or not raw_role_title.strip():
        return "Other"

    normalized = _normalize(raw_role_title)

    for level, substr_tokens, pattern in _SENIORITY_RULES:
        if level == "Mid" and _ROMAN_PATTERN.search(normalized):
            return "Mid"
        for token in substr_tokens:
            if token in normalized:
                return level
        if pattern and pattern.search(normalized):
            return level

    return "Other"
