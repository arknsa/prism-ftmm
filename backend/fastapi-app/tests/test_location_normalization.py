"""Tests for location_normalization.py (P3.8).

Covers all testable invariants from Artifact A3 (GEOGRAPHIC_CANONICAL_SPEC.md §6):
1. Blank/absent input → None returned (no row created).
2. Remote sentinel keywords → Remote LOCATION row returned.
3. Same raw string → same LOCATION row (idempotent via first-sight).
4. First-sight: unknown string creates exactly one LOCATION row.
5. Known city string → seeded row returned (exact city match).
6. No country token → country defaults to "Indonesia".
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

from app.models.reference import Location
from app.services.location_normalization import (
    _extract_country,
    resolve_location,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_location(
    location_id: int = 1,
    country: str = "Indonesia",
    province: str | None = None,
    city: str | None = None,
    region: str | None = None,
) -> MagicMock:
    loc = MagicMock(spec=Location)
    loc.location_id = location_id
    loc.country = country
    loc.province = province
    loc.city = city
    loc.region = region
    return loc


def _session_no_match() -> MagicMock:
    session = create_autospec(Session, instance=True)
    session.scalar.return_value = None
    session.flush = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Invariant 1 — blank/absent → None
# ---------------------------------------------------------------------------


class TestBlankInput:
    def test_none_returns_none(self) -> None:
        session = create_autospec(Session, instance=True)
        assert resolve_location(None, session) is None

    def test_empty_string_returns_none(self) -> None:
        session = create_autospec(Session, instance=True)
        assert resolve_location("", session) is None

    def test_whitespace_only_returns_none(self) -> None:
        session = create_autospec(Session, instance=True)
        assert resolve_location("   ", session) is None

    def test_no_db_calls_on_blank(self) -> None:
        session = create_autospec(Session, instance=True)
        resolve_location(None, session)
        session.scalar.assert_not_called()
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Invariant 2 — Remote sentinel
# ---------------------------------------------------------------------------


class TestRemoteSentinel:
    def setup_method(self) -> None:
        self.remote_row = _make_location(location_id=99, country="Remote", region="Remote")

    def _session_with_remote(self) -> MagicMock:
        session = create_autospec(Session, instance=True)
        session.scalar.return_value = self.remote_row
        return session

    def test_remote_keyword_returns_sentinel(self) -> None:
        result = resolve_location("Remote", self._session_with_remote())
        assert result is self.remote_row

    def test_wfh_returns_sentinel(self) -> None:
        result = resolve_location("WFH", self._session_with_remote())
        assert result is self.remote_row

    def test_work_from_home_returns_sentinel(self) -> None:
        result = resolve_location("Work from Home", self._session_with_remote())
        assert result is self.remote_row

    def test_work_from_home_hyphen(self) -> None:
        result = resolve_location("Work-from-Home", self._session_with_remote())
        assert result is self.remote_row

    def test_remote_case_insensitive(self) -> None:
        result = resolve_location("REMOTE", self._session_with_remote())
        assert result is self.remote_row

    def test_no_city_created_for_remote(self) -> None:
        session = self._session_with_remote()
        resolve_location("Remote", session)
        session.add.assert_not_called()

    def test_creates_remote_sentinel_if_not_seeded(self) -> None:
        session = create_autospec(Session, instance=True)
        session.scalar.return_value = None
        session.flush = MagicMock()
        added: list[object] = []
        session.add = lambda obj: added.append(obj)

        result = resolve_location("Remote", session)

        assert isinstance(result, Location)
        assert result.country == "Remote"
        assert result.region == "Remote"
        assert len(added) == 1


# ---------------------------------------------------------------------------
# Invariant 5 — Known city matches seeded row
# ---------------------------------------------------------------------------


class TestKnownCityMatch:
    def setup_method(self) -> None:
        self.jakarta_row = _make_location(
            location_id=5, country="Indonesia", province="DKI Jakarta", city="Jakarta"
        )

    def _session_returning_city(self) -> MagicMock:
        session = create_autospec(Session, instance=True)
        session.scalar.return_value = self.jakarta_row
        return session

    def test_known_city_returns_seeded_row(self) -> None:
        result = resolve_location("Jakarta", self._session_returning_city())
        assert result is self.jakarta_row

    def test_known_city_no_new_row_created(self) -> None:
        session = self._session_returning_city()
        resolve_location("Jakarta", session)
        session.add.assert_not_called()

    def test_known_city_with_country(self) -> None:
        result = resolve_location("Jakarta Indonesia", self._session_returning_city())
        assert result is self.jakarta_row

    def test_city_with_comma(self) -> None:
        result = resolve_location("Jakarta, Indonesia", self._session_returning_city())
        assert result is self.jakarta_row


# ---------------------------------------------------------------------------
# Invariant 4 — First-sight: unknown string → exactly one LOCATION created
# ---------------------------------------------------------------------------


class TestFirstSightCreation:
    def test_unknown_city_creates_one_location(self) -> None:
        session = _session_no_match()
        added: list[object] = []
        session.add = lambda obj: added.append(obj)

        result = resolve_location("Nowhere City", session)

        assert isinstance(result, Location)
        assert len(added) == 1
        assert result is added[0]

    def test_first_sight_country_defaults_to_indonesia(self) -> None:
        session = _session_no_match()
        added: list[object] = []
        session.add = lambda obj: added.append(obj)

        resolve_location("Nowhere City", session)

        new_loc = added[0]
        assert isinstance(new_loc, Location)
        assert new_loc.country == "Indonesia"

    def test_first_sight_known_country_used(self) -> None:
        session = _session_no_match()
        added: list[object] = []
        session.add = lambda obj: added.append(obj)

        resolve_location("Berlin Germany", session)

        new_loc = added[0]
        assert isinstance(new_loc, Location)
        assert new_loc.country == "Germany"

    def test_flush_called_on_first_sight(self) -> None:
        session = _session_no_match()
        resolve_location("Unknown Place", session)
        session.flush.assert_called_once()

    def test_city_extracted_from_single_token(self) -> None:
        session = _session_no_match()
        added: list[object] = []
        session.add = lambda obj: added.append(obj)

        resolve_location("Kediri", session)

        new_loc = added[0]
        assert isinstance(new_loc, Location)
        assert new_loc.city == "Kediri"
        assert new_loc.country == "Indonesia"


# ---------------------------------------------------------------------------
# Invariant 6 — No country token → default Indonesia
# ---------------------------------------------------------------------------


class TestCountryDefaulting:
    def test_no_country_token_defaults_to_indonesia(self) -> None:
        country, _ = _extract_country("Surabaya")
        assert country == "Indonesia"

    def test_known_country_token_extracted(self) -> None:
        country, remaining = _extract_country("Jakarta Indonesia")
        assert country == "Indonesia"
        assert "Jakarta" in remaining or "jakarta" in [t.lower() for t in remaining]

    def test_singapore_extracted(self) -> None:
        country, remaining = _extract_country("Singapore")
        assert country == "Singapore"

    def test_usa_alias(self) -> None:
        country, _ = _extract_country("San Francisco USA")
        assert country == "United States"

    def test_uk_alias(self) -> None:
        country, _ = _extract_country("London UK")
        assert country == "United Kingdom"

    def test_multi_word_country_extracted(self) -> None:
        country, _ = _extract_country("New York United States")
        assert country == "United States"

    def test_south_korea(self) -> None:
        country, _ = _extract_country("Seoul South Korea")
        assert country == "South Korea"


# ---------------------------------------------------------------------------
# Invariant 3 — Idempotent: same input → same row
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_call_with_same_text_returns_same_row(self) -> None:
        existing = _make_location(location_id=42, country="Indonesia", city="Kediri")
        session = create_autospec(Session, instance=True)
        session.scalar.return_value = existing

        result1 = resolve_location("Kediri", session)
        result2 = resolve_location("Kediri", session)

        assert result1 is existing
        assert result2 is existing
        # No new rows created on second call
        session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Province match fallback
# ---------------------------------------------------------------------------


class TestProvinceMatch:
    def setup_method(self) -> None:
        self.province_row = _make_location(
            location_id=18, country="Indonesia", province="East Java", city=None
        )

    def test_province_match_returns_province_row(self) -> None:
        session = create_autospec(Session, instance=True)
        # First scalar call (city match) returns None; second (province) returns row
        session.scalar.side_effect = [None, self.province_row]

        result = resolve_location("East Java", session)

        assert result is self.province_row
        session.add.assert_not_called()
