"""Unit tests for app.services.import_parser (P3.1, P3.2).

All tests run in pure isolation: no real database, no file system beyond the
fixtures checked into tests/fixtures/. SQLAlchemy sessions are replaced with
create_autospec(Session) following the established Phase 1/2 test pattern.

Coverage:
- Valid CSV files for all three sources.
- XLSX file parsing.
- Per-row error recording (missing required field, bad graduation_year).
- Extra columns captured in raw_extra.
- Optional fields correctly NULLed when absent.
- Unknown source type raises ValueError.
- Unsupported file extension raises ValueError.
- ImportBatch metadata (counts, status) correct.
- Determinism: same input → same output.
- StagingRow objects added to session for every body row.

Decisions: D-033, D-005.
"""

from __future__ import annotations

import io
import pathlib
from unittest.mock import MagicMock, create_autospec

import openpyxl
import pytest
from app.models.staging import ImportBatch, StagingRow
from app.services.import_parser import SUPPORTED_SOURCES, parse_import
from sqlalchemy.orm import Session

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a spec'd mock Session; flush() populates batch_id via side effect."""
    session = create_autospec(Session, instance=True)

    def _flush_side_effect() -> None:
        # Simulate the DB assigning batch_id after flush so FK on StagingRow is valid.
        for added_call in session.add.call_args_list:
            obj = added_call.args[0]
            if isinstance(obj, ImportBatch) and obj.batch_id is None:
                obj.batch_id = 1

    session.flush.side_effect = _flush_side_effect
    return session


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    """Build a CSV bytes object from a list of row dicts (keys = headers)."""
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(row.get(h, "") for h in headers))
    return "\n".join(lines).encode("utf-8")


def _xlsx_bytes(rows: list[dict[str, str]]) -> bytes:
    """Build an XLSX bytes object from a list of row dicts."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    if not rows:
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _added_staging_rows(session: MagicMock) -> list[StagingRow]:
    return [a.args[0] for a in session.add.call_args_list if isinstance(a.args[0], StagingRow)]


# ---------------------------------------------------------------------------
# Fixture file loading
# ---------------------------------------------------------------------------


class TestFixtureFiles:
    """The sample CSV fixtures parse without error rows."""

    def test_linkedin_fixture_all_valid(self) -> None:
        content = (FIXTURES / "sample_linkedin.csv").read_bytes()
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="sample_linkedin.csv",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.total_rows == 6
        assert batch.error_rows == 0
        assert batch.parsed_rows == 6
        assert batch.status == "complete"

    def test_verified_fixture_has_employer_absent_row(self) -> None:
        content = (FIXTURES / "sample_verified.csv").read_bytes()
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="sample_verified.csv",
            source_type="Verified Faculty Record",
            source_id=1,
            session=session,
        )
        # Fajar Nugroho row has no employer — still valid (employer optional for Verified)
        assert batch.total_rows == 4
        assert batch.error_rows == 0
        rows = _added_staging_rows(session)
        fajar = next(r for r in rows if r.raw_full_name == "Fajar Nugroho")
        assert fajar.raw_employer is None
        assert fajar.row_status == "pending"

    def test_tracer_fixture_employed_status_in_extra(self) -> None:
        content = (FIXTURES / "sample_tracer.csv").read_bytes()
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="sample_tracer.csv",
            source_type="Tracer Study",
            source_id=2,
            session=session,
        )
        assert batch.error_rows == 0
        rows = _added_staging_rows(session)
        # employed_status is optional per Tracer spec — goes to raw_extra
        bagas = next(r for r in rows if r.raw_full_name == "Bagas Saputra")
        assert bagas.raw_extra is not None
        assert bagas.raw_extra.get("employed_status") == "Employed"


# ---------------------------------------------------------------------------
# LinkedIn source
# ---------------------------------------------------------------------------


class TestLinkedInSource:
    SOURCE = "LinkedIn"
    SOURCE_ID = 3

    def _parse(
        self, rows: list[dict[str, str]], filename: str = "test.csv"
    ) -> tuple[ImportBatch, MagicMock]:
        session = _make_session()
        batch = parse_import(
            file_content=_csv_bytes(rows),
            filename=filename,
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=session,
        )
        return batch, session

    def test_valid_row_staged_as_pending(self) -> None:
        rows = [
            {
                "full_name": "Budi Santoso",
                "study_program": "Technology of Data Science",
                "graduation_year": "2022",
                "employer": "Gojek",
                "role_title": "Analyst",
                "location": "Jakarta",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.total_rows == 1
        assert batch.parsed_rows == 1
        assert batch.error_rows == 0
        staged = _added_staging_rows(session)
        assert len(staged) == 1
        r = staged[0]
        assert r.raw_full_name == "Budi Santoso"
        assert r.raw_study_program == "Technology of Data Science"
        assert r.raw_graduation_year == 2022
        assert r.raw_employer == "Gojek"
        assert r.raw_role_title == "Analyst"
        assert r.raw_location == "Jakarta"
        assert r.raw_linkedin_url is None
        assert r.row_status == "pending"
        assert r.row_error is None

    def test_missing_required_field_employer_records_error(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "",
                "role_title": "Engineer",
                "location": "Surabaya",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 1
        assert batch.parsed_rows == 0
        staged = _added_staging_rows(session)
        assert staged[0].row_status == "error"
        assert "employer" in (staged[0].row_error or "")

    def test_missing_full_name_records_error(self) -> None:
        rows = [
            {
                "full_name": "",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Engineer",
                "location": "Jakarta",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 1
        assert "full_name" in (_added_staging_rows(session)[0].row_error or "")

    def test_invalid_graduation_year_records_error(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "not-a-year",
                "employer": "ACME",
                "role_title": "Engineer",
                "location": "Jakarta",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 1
        assert "graduation_year" in (_added_staging_rows(session)[0].row_error or "")

    def test_graduation_year_out_of_range_records_error(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "1800",
                "employer": "ACME",
                "role_title": "Engineer",
                "location": "Jakarta",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 1

    def test_xlsx_float_year_accepted(self) -> None:
        """XLSX numeric cells often come through as '2022.0' — must still parse."""
        rows = [
            {
                "full_name": "Y",
                "study_program": "Electrical Engineering",
                "graduation_year": "2022.0",
                "employer": "PLN",
                "role_title": "Engineer",
                "location": "Bandung",
            }
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 0
        assert _added_staging_rows(session)[0].raw_graduation_year == 2022

    def test_optional_linkedin_url_captured(self) -> None:
        rows = [
            {
                "full_name": "Z",
                "study_program": "Technology of Data Science",
                "graduation_year": "2023",
                "employer": "Tokopedia",
                "role_title": "DS",
                "location": "Jakarta",
                "linkedin_url": "https://linkedin.com/in/z",
            }
        ]
        _, session = self._parse(rows)
        assert _added_staging_rows(session)[0].raw_linkedin_url == "https://linkedin.com/in/z"

    def test_extra_columns_in_raw_extra(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
                "custom_col": "custom_value",
            }
        ]
        _, session = self._parse(rows)
        extra = _added_staging_rows(session)[0].raw_extra
        assert extra is not None
        assert extra.get("custom_col") == "custom_value"

    def test_spec_columns_not_in_raw_extra(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
                "linkedin_url": "https://li.com/x",
            }
        ]
        _, session = self._parse(rows)
        extra = _added_staging_rows(session)[0].raw_extra
        # linkedin_url is a spec col — must NOT appear in raw_extra
        assert extra is None or "linkedin_url" not in extra

    def test_mixed_valid_and_error_rows(self) -> None:
        rows = [
            {
                "full_name": "Good",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            },
            {
                "full_name": "",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            },
        ]
        batch, session = self._parse(rows)
        assert batch.total_rows == 2
        assert batch.parsed_rows == 1
        assert batch.error_rows == 1
        staged = _added_staging_rows(session)
        assert any(r.row_status == "pending" for r in staged)
        assert any(r.row_status == "error" for r in staged)

    def test_row_numbers_are_correct(self) -> None:
        rows = [
            {
                "full_name": "A",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "X",
                "role_title": "E",
                "location": "J",
            },
            {
                "full_name": "B",
                "study_program": "Industrial Engineering",
                "graduation_year": "2022",
                "employer": "Y",
                "role_title": "F",
                "location": "S",
            },
        ]
        _, session = self._parse(rows)
        staged = _added_staging_rows(session)
        assert staged[0].row_number == 2  # header = row 1
        assert staged[1].row_number == 3

    def test_determinism(self) -> None:
        """Same file + same source → identical staged rows."""
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        content = _csv_bytes(rows)

        s1 = _make_session()
        parse_import(
            file_content=content,
            filename="f.csv",
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=s1,
        )
        s2 = _make_session()
        parse_import(
            file_content=content,
            filename="f.csv",
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=s2,
        )

        r1 = _added_staging_rows(s1)[0]
        r2 = _added_staging_rows(s2)[0]
        assert r1.raw_full_name == r2.raw_full_name
        assert r1.raw_graduation_year == r2.raw_graduation_year
        assert r1.row_status == r2.row_status

    def test_batch_metadata_recorded(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        batch, _ = self._parse(rows, filename="my_file.csv")
        assert batch.filename == "my_file.csv"
        assert batch.source_id == self.SOURCE_ID
        assert batch.status == "complete"

    def test_session_flush_called_for_batch_id(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        _, session = self._parse(rows)
        session.flush.assert_called_once()

    def test_created_by_none_for_system_import(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        batch, _ = self._parse(rows)
        assert batch.created_by is None

    def test_created_by_propagated(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        session = _make_session()
        batch = parse_import(
            file_content=_csv_bytes(rows),
            filename="f.csv",
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=session,
            created_by=7,
        )
        assert batch.created_by == 7


# ---------------------------------------------------------------------------
# Verified Faculty Record source
# ---------------------------------------------------------------------------


class TestVerifiedSource:
    SOURCE = "Verified Faculty Record"
    SOURCE_ID = 1

    def _parse(self, rows: list[dict[str, str]]) -> tuple[ImportBatch, MagicMock]:
        session = _make_session()
        batch = parse_import(
            file_content=_csv_bytes(rows),
            filename="verified.csv",
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=session,
        )
        return batch, session

    def test_employer_absent_valid_row(self) -> None:
        rows = [
            {"full_name": "X", "study_program": "Industrial Engineering", "graduation_year": "2023"}
        ]
        batch, session = self._parse(rows)
        assert batch.error_rows == 0
        r = _added_staging_rows(session)[0]
        assert r.raw_employer is None
        assert r.row_status == "pending"

    def test_missing_full_name_is_error(self) -> None:
        rows = [
            {"full_name": "", "study_program": "Industrial Engineering", "graduation_year": "2022"}
        ]
        batch, _ = self._parse(rows)
        assert batch.error_rows == 1

    def test_employer_present_captured(self) -> None:
        rows = [
            {
                "full_name": "Y",
                "study_program": "Electrical Engineering",
                "graduation_year": "2021",
                "employer": "PLN",
                "role_title": "Eng",
                "location": "Bandung",
            }
        ]
        _, session = self._parse(rows)
        r = _added_staging_rows(session)[0]
        assert r.raw_employer == "PLN"
        assert r.raw_role_title == "Eng"

    def test_notes_in_raw_extra(self) -> None:
        rows = [
            {
                "full_name": "Z",
                "study_program": "Electrical Engineering",
                "graduation_year": "2020",
                "notes": "special note",
            }
        ]
        _, session = self._parse(rows)
        extra = _added_staging_rows(session)[0].raw_extra
        assert extra is not None
        assert extra.get("notes") == "special note"


# ---------------------------------------------------------------------------
# Tracer Study source
# ---------------------------------------------------------------------------


class TestTracerSource:
    SOURCE = "Tracer Study"
    SOURCE_ID = 2

    def _parse(self, rows: list[dict[str, str]]) -> tuple[ImportBatch, MagicMock]:
        session = _make_session()
        batch = parse_import(
            file_content=_csv_bytes(rows),
            filename="tracer.csv",
            source_type=self.SOURCE,
            source_id=self.SOURCE_ID,
            session=session,
        )
        return batch, session

    def test_employed_status_not_in_candidate_shape(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Technology of Data Science",
                "graduation_year": "2022",
                "employed_status": "Employed",
            }
        ]
        _, session = self._parse(rows)
        r = _added_staging_rows(session)[0]
        # employed_status does not map to a staging field; goes to raw_extra
        assert r.raw_extra is not None
        assert r.raw_extra.get("employed_status") == "Employed"
        assert r.row_status == "pending"

    def test_missing_graduation_year_records_error(self) -> None:
        rows = [
            {"full_name": "Y", "study_program": "Industrial Engineering", "graduation_year": ""}
        ]
        batch, _ = self._parse(rows)
        assert batch.error_rows == 1


# ---------------------------------------------------------------------------
# XLSX parsing
# ---------------------------------------------------------------------------


class TestXlsxParsing:
    def test_valid_xlsx_linkedin(self) -> None:
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        content = _xlsx_bytes(rows)
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="import.xlsx",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.total_rows == 1
        assert batch.error_rows == 0
        staged = _added_staging_rows(session)
        assert staged[0].raw_employer == "ACME"

    def test_xlsx_float_graduation_year(self) -> None:
        """XLSX numeric cells parsed as float strings ('2022.0') must still produce int year."""
        rows = [
            {
                "full_name": "X",
                "study_program": "Industrial Engineering",
                "graduation_year": "2022.0",
                "employer": "X",
                "role_title": "E",
                "location": "J",
            }
        ]
        content = _xlsx_bytes(rows)
        session = _make_session()
        parse_import(
            file_content=content,
            filename="x.xlsx",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert _added_staging_rows(session)[0].raw_graduation_year == 2022

    def test_xlsx_real_fixture(self) -> None:
        """Round-trip: build an XLSX from the same data as sample_linkedin.csv and parse it."""
        rows = [
            {
                "full_name": "Budi Santoso",
                "study_program": "Technology of Data Science",
                "graduation_year": "2022",
                "employer": "PT Gojek Indonesia",
                "role_title": "Data Analyst",
                "location": "Jakarta Indonesia",
            },
        ]
        content = _xlsx_bytes(rows)
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="linkedin.xlsx",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.error_rows == 0
        assert _added_staging_rows(session)[0].raw_full_name == "Budi Santoso"


# ---------------------------------------------------------------------------
# Error / boundary cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    def test_unknown_source_type_raises(self) -> None:
        session = _make_session()
        with pytest.raises(ValueError, match="Unknown source type"):
            parse_import(
                file_content=b"col\nval",
                filename="f.csv",
                source_type="NonExistent",
                source_id=1,
                session=session,
            )

    def test_unsupported_extension_raises(self) -> None:
        session = _make_session()
        with pytest.raises(ValueError, match="Unsupported file extension"):
            parse_import(
                file_content=b"data",
                filename="import.txt",
                source_type="LinkedIn",
                source_id=3,
                session=session,
            )

    def test_supported_sources_constant(self) -> None:
        assert "LinkedIn" in SUPPORTED_SOURCES
        assert "Verified Faculty Record" in SUPPORTED_SOURCES
        assert "Tracer Study" in SUPPORTED_SOURCES

    def test_empty_csv_produces_no_staging_rows(self) -> None:
        session = _make_session()
        batch = parse_import(
            file_content=b"full_name,study_program,graduation_year,employer,role_title,location\n",
            filename="empty.csv",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.total_rows == 0
        assert batch.error_rows == 0
        assert _added_staging_rows(session) == []

    def test_whitespace_only_required_field_is_error(self) -> None:
        rows = [
            {
                "full_name": "   ",
                "study_program": "Industrial Engineering",
                "graduation_year": "2021",
                "employer": "ACME",
                "role_title": "Eng",
                "location": "Jkt",
            }
        ]
        session = _make_session()
        batch = parse_import(
            file_content=_csv_bytes(rows),
            filename="ws.csv",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.error_rows == 1

    def test_column_names_case_insensitive(self) -> None:
        """Headers in UPPER_CASE still map to spec columns."""
        content = (
            b"FULL_NAME,STUDY_PROGRAM,GRADUATION_YEAR,EMPLOYER,ROLE_TITLE,LOCATION\n"
            b"X,Industrial Engineering,2021,ACME,Eng,Jkt\n"
        )
        session = _make_session()
        batch = parse_import(
            file_content=content,
            filename="upper.csv",
            source_type="LinkedIn",
            source_id=3,
            session=session,
        )
        assert batch.error_rows == 0
        assert _added_staging_rows(session)[0].raw_full_name == "X"
