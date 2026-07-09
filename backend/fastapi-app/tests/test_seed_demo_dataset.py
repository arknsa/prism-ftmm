"""Tests for the seed_demo_dataset safety safeguards (M4).

These exercise the C1 preflight (production guard, confirmation requirement, non-demo
data protection, empty DB, demo fingerprint) and the H3 lookup-validation guard —
without a real database, using a fake connection. No production code is modified.

The script lives in scripts/imports/; it is imported by path here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

# --- Import the standalone seed script (scripts/imports/seed_demo_dataset.py) ---
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts" / "imports"
sys.path.insert(0, str(_SCRIPTS_DIR))  # so its `from _utils import ...` resolves
_spec = importlib.util.spec_from_file_location(
    "seed_demo_dataset", _SCRIPTS_DIR / "seed_demo_dataset.py"
)
assert _spec and _spec.loader
seed_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_demo)


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value


class _FakeConn:
    """Minimal Connection stand-in: every execute() returns the configured count."""

    def __init__(self, alumni_count: int = 0) -> None:
        self._count = alumni_count

    def execute(self, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self._count)


@pytest.fixture(autouse=True)
def _clear_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: no APP_ENV (non-production) unless a test sets it."""
    monkeypatch.delenv("APP_ENV", raising=False)


# ---------------------------------------------------------------------------
# Preflight: production guard
# ---------------------------------------------------------------------------


def test_preflight_refuses_on_production_even_when_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SystemExit) as exc:
        seed_demo._preflight_or_abort(_FakeConn(0), forced=True, target_host="h")
    assert exc.value.code == seed_demo._REFUSED_EXIT


def test_preflight_production_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "Production")
    with pytest.raises(SystemExit):
        seed_demo._preflight_or_abort(_FakeConn(0), forced=True, target_host="h")


# ---------------------------------------------------------------------------
# Preflight: confirmation requirement
# ---------------------------------------------------------------------------


def test_preflight_refuses_without_confirmation() -> None:
    with pytest.raises(SystemExit) as exc:
        seed_demo._preflight_or_abort(_FakeConn(0), forced=False, target_host="h")
    assert exc.value.code == seed_demo._REFUSED_EXIT


# ---------------------------------------------------------------------------
# Preflight: non-demo data protection
# ---------------------------------------------------------------------------


def test_preflight_refuses_when_target_has_non_demo_data() -> None:
    # 399 != 0 and != fingerprint(400) => treated as real/ingested data.
    with pytest.raises(SystemExit) as exc:
        seed_demo._preflight_or_abort(_FakeConn(399), forced=True, target_host="h")
    assert exc.value.code == seed_demo._REFUSED_EXIT


def test_preflight_refuses_on_large_real_dataset() -> None:
    with pytest.raises(SystemExit):
        seed_demo._preflight_or_abort(_FakeConn(1_000_000), forced=True, target_host="h")


# ---------------------------------------------------------------------------
# Preflight: allowed cases (empty DB, demo fingerprint)
# ---------------------------------------------------------------------------


def test_preflight_allows_empty_database_when_forced() -> None:
    # Should NOT raise.
    seed_demo._preflight_or_abort(_FakeConn(0), forced=True, target_host="h")


def test_preflight_allows_demo_fingerprint_when_forced() -> None:
    seed_demo._preflight_or_abort(
        _FakeConn(seed_demo._DEMO_ALUMNI_FINGERPRINT), forced=True, target_host="h"
    )


def test_fingerprint_matches_total_alumni() -> None:
    # Guard against drift: the fingerprint must equal the number the script inserts.
    assert seed_demo._DEMO_ALUMNI_FINGERPRINT == seed_demo.TOTAL_ALUMNI


# ---------------------------------------------------------------------------
# Lookup validation (H3): demo reference values must exist in lookup tables
# ---------------------------------------------------------------------------


def test_all_company_industries_and_cities_are_referenced_consistently() -> None:
    """Every COMPANIES industry/city is a plain non-empty string (resolved at runtime
    against the seeded lookups). This asserts the demo data shape the H3 guard checks."""
    for canonical, industry, city, aliases in seed_demo.COMPANIES:
        assert isinstance(canonical, str) and canonical
        assert isinstance(industry, str) and industry
        assert isinstance(city, str) and city
        assert isinstance(aliases, list)


def test_company_industry_names_are_unique_per_company_entry() -> None:
    # canonical_name is unique (DB constraint) — the demo data must not duplicate it.
    names = [c[0] for c in seed_demo.COMPANIES]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# _host_of: never leaks credentials
# ---------------------------------------------------------------------------


def test_host_of_strips_credentials() -> None:
    url = "postgresql://user:secretpw@db.example.com:6543/postgres"
    host = seed_demo._host_of(url)
    assert "secretpw" not in host
    assert "user" not in host
    assert host == "db.example.com:6543"


def test_host_of_handles_malformed_url() -> None:
    assert seed_demo._host_of("not-a-url") in ("unknown", "not-a-url")
