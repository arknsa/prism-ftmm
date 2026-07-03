"""Import parser service (P3.2).

Reads a CSV or XLSX file for a declared source type, maps columns to the
common staging shape defined by Artifact A1 (IMPORT_FILE_FORMAT_SPEC.md),
and returns a populated ImportBatch with associated StagingRow objects added
to the SQLAlchemy session (not yet committed — caller owns the transaction).

Design constraints:
- Deterministic: same file + same source → same staged rows (no inference).
- Non-lossy: malformed rows get row_status="error"; nothing is silently dropped.
- No audit wiring here — that is S2 (P3.3).
- Supported sources: "LinkedIn", "Verified Faculty Record", "Tracer Study" (D-005).

Decisions: D-033, D-005, D-046 (source_id provenance).
"""

from __future__ import annotations

import csv
import datetime
import io
import logging
from dataclasses import dataclass
from typing import Any

import openpyxl
from sqlalchemy.orm import Session

from app.models.staging import ImportBatch, StagingRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported source types (D-005; matches CAPTURE_SOURCE.source_type seed values)
# ---------------------------------------------------------------------------

SUPPORTED_SOURCES: frozenset[str] = frozenset(
    {"LinkedIn", "Verified Faculty Record", "Tracer Study"}
)

# ---------------------------------------------------------------------------
# Column specs per source (Artifact A1 — IMPORT_FILE_FORMAT_SPEC.md)
#
# _REQUIRED:       missing/blank value → row_status="error"
# _NAMED_OPTIONAL: absent or blank → NULL on the named staging field
# _EXTRA_ROUTED:   recognized A1 column whose value goes to raw_extra, not a
#                  named field (e.g. "notes", "employed_status")
#
# _ALL_NAMED_COLS = _REQUIRED | _NAMED_OPTIONAL
#   → columns excluded from the raw_extra dict (they have dedicated fields)
# Columns not in _ALL_NAMED_COLS land in raw_extra.
# ---------------------------------------------------------------------------

_REQUIRED: dict[str, list[str]] = {
    "LinkedIn": [
        "full_name",
        "study_program",
        "graduation_year",
        "employer",
        "role_title",
        "location",
    ],
    "Verified Faculty Record": ["full_name", "study_program", "graduation_year"],
    "Tracer Study": ["full_name", "study_program", "graduation_year"],
}

# Optional columns that map to named staging fields (raw_full_name, raw_employer, …)
_NAMED_OPTIONAL: dict[str, list[str]] = {
    "LinkedIn": ["linkedin_url"],
    "Verified Faculty Record": ["employer", "role_title", "location", "linkedin_url"],
    "Tracer Study": ["employer", "role_title", "location", "linkedin_url"],
}

# Columns excluded from raw_extra — they map to named staging fields
_ALL_NAMED_COLS: dict[str, frozenset[str]] = {
    src: frozenset(_REQUIRED[src]) | frozenset(_NAMED_OPTIONAL[src]) for src in SUPPORTED_SOURCES
}


# ---------------------------------------------------------------------------
# Internal row representation
# ---------------------------------------------------------------------------


@dataclass
class _ParsedRow:
    row_number: int
    raw_full_name: str | None
    raw_study_program: str | None
    raw_graduation_year: int | None
    raw_employer: str | None
    raw_role_title: str | None
    raw_location: str | None
    raw_linkedin_url: str | None
    raw_extra: dict[str, Any]
    row_status: str  # "pending" | "error"
    row_error: str | None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def parse_import(
    *,
    file_content: bytes,
    filename: str,
    source_type: str,
    source_id: int,
    session: Session,
    created_by: int | None = None,
) -> ImportBatch:
    """Parse a CSV/XLSX file and stage all rows.

    Creates one ImportBatch and N StagingRow objects, all added to `session`.
    The caller must flush/commit when ready (no audit wiring here — that is S2).

    Args:
        file_content: raw bytes of the uploaded file.
        filename: original filename (stored on ImportBatch).
        source_type: one of the SUPPORTED_SOURCES strings.
        source_id: FK to CAPTURE_SOURCE (must match source_type; caller resolves).
        session: active SQLAlchemy session — objects are added but not committed.
        created_by: AppUser.user_id of the actor; None for CLI/system imports.

    Returns:
        The ImportBatch instance (added to session, not yet committed).

    Raises:
        ValueError: unknown source_type or unreadable file format.
    """
    if source_type not in SUPPORTED_SOURCES:
        raise ValueError(
            f"Unknown source type {source_type!r}. " f"Supported: {sorted(SUPPORTED_SOURCES)}"
        )

    rows = _read_file(file_content, filename)
    parsed = _parse_rows(rows, source_type)

    total = len(parsed)
    errors = sum(1 for r in parsed if r.row_status == "error")
    parsed_ok = total - errors

    batch = ImportBatch(
        source_id=source_id,
        filename=filename,
        total_rows=total,
        parsed_rows=parsed_ok,
        error_rows=errors,
        status="complete",
        created_by=created_by,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    session.add(batch)
    session.flush()  # populate batch_id so FK is valid on staging rows

    for p in parsed:
        row = StagingRow(
            batch_id=batch.batch_id,
            row_number=p.row_number,
            raw_full_name=p.raw_full_name,
            raw_study_program=p.raw_study_program,
            raw_graduation_year=p.raw_graduation_year,
            raw_employer=p.raw_employer,
            raw_role_title=p.raw_role_title,
            raw_location=p.raw_location,
            raw_linkedin_url=p.raw_linkedin_url,
            raw_extra=p.raw_extra if p.raw_extra else None,
            row_status=p.row_status,
            row_error=p.row_error,
        )
        session.add(row)

    logger.info(
        "import_parser: source=%r filename=%r total=%d parsed=%d errors=%d",
        source_type,
        filename,
        total,
        parsed_ok,
        errors,
    )
    return batch


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------


def _read_file(content: bytes, filename: str) -> list[dict[str, str]]:
    """Return a list of {header: cell_string} dicts, one per body row.

    Raises ValueError for unsupported file extensions or unreadable content.
    Column names are normalised (stripped, lowercased) at read time.
    """
    lower = filename.lower()
    if lower.endswith(".csv"):
        return _read_csv(content)
    if lower.endswith(".xlsx"):
        return _read_xlsx(content)
    raise ValueError(
        f"Unsupported file extension for {filename!r}. " "Only .csv and .xlsx files are accepted."
    )


def _read_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        rows.append({k.strip().lower(): (v or "").strip() for k, v in raw_row.items()})
    return rows


def _read_xlsx(content: bytes) -> list[dict[str, str]]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        ws = wb.active
        if ws is None:
            raise ValueError("XLSX file has no active worksheet.")

        rows_iter = ws.iter_rows(values_only=True)
        try:
            raw_header = next(rows_iter)
        except StopIteration:
            return []

        headers = [str(h).strip().lower() if h is not None else "" for h in raw_header]
        result: list[dict[str, str]] = []
        for raw_row in rows_iter:
            row_dict: dict[str, str] = {}
            for h, cell in zip(headers, raw_row, strict=False):
                row_dict[h] = str(cell).strip() if cell is not None else ""
            result.append(row_dict)
    finally:
        wb.close()
    return result


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def _parse_rows(rows: list[dict[str, str]], source_type: str) -> list[_ParsedRow]:
    required = _REQUIRED[source_type]
    spec_cols = _ALL_NAMED_COLS[source_type]
    parsed: list[_ParsedRow] = []

    for idx, raw in enumerate(rows):
        row_number = idx + 2  # header = row 1; first body row = row 2

        # Check required fields
        missing = [col for col in required if not raw.get(col)]
        if missing:
            parsed.append(
                _ParsedRow(
                    row_number=row_number,
                    raw_full_name=_str_or_none(raw.get("full_name")),
                    raw_study_program=_str_or_none(raw.get("study_program")),
                    raw_graduation_year=None,
                    raw_employer=_str_or_none(raw.get("employer")),
                    raw_role_title=_str_or_none(raw.get("role_title")),
                    raw_location=_str_or_none(raw.get("location")),
                    raw_linkedin_url=_str_or_none(raw.get("linkedin_url")),
                    raw_extra=_extra(raw, spec_cols),
                    row_status="error",
                    row_error=f"Missing required field(s): {', '.join(missing)}",
                )
            )
            continue

        # Parse graduation_year as integer
        grad_year, year_error = _parse_year(raw.get("graduation_year", ""))
        if year_error:
            parsed.append(
                _ParsedRow(
                    row_number=row_number,
                    raw_full_name=_str_or_none(raw.get("full_name")),
                    raw_study_program=_str_or_none(raw.get("study_program")),
                    raw_graduation_year=None,
                    raw_employer=_str_or_none(raw.get("employer")),
                    raw_role_title=_str_or_none(raw.get("role_title")),
                    raw_location=_str_or_none(raw.get("location")),
                    raw_linkedin_url=_str_or_none(raw.get("linkedin_url")),
                    raw_extra=_extra(raw, spec_cols),
                    row_status="error",
                    row_error=year_error,
                )
            )
            continue

        parsed.append(
            _ParsedRow(
                row_number=row_number,
                raw_full_name=_str_or_none(raw.get("full_name")),
                raw_study_program=_str_or_none(raw.get("study_program")),
                raw_graduation_year=grad_year,
                raw_employer=_str_or_none(raw.get("employer")),
                raw_role_title=_str_or_none(raw.get("role_title")),
                raw_location=_str_or_none(raw.get("location")),
                raw_linkedin_url=_str_or_none(raw.get("linkedin_url")),
                raw_extra=_extra(raw, spec_cols),
                row_status="pending",
                row_error=None,
            )
        )

    return parsed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _str_or_none(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _parse_year(raw: str) -> tuple[int | None, str | None]:
    """Return (year_int, None) on success or (None, error_msg) on failure."""
    clean = raw.strip()
    if not clean:
        return None, "graduation_year is required but was empty"
    # Accept values like "2022" or "2022.0" (common in XLSX numeric cells)
    try:
        as_float = float(clean)
        year = int(as_float)
        if year < 1900 or year > 2100:
            return None, f"graduation_year {year!r} is out of plausible range (1900–2100)"
        return year, None
    except ValueError:
        return None, f"graduation_year {clean!r} is not a valid integer year"


def _extra(raw: dict[str, str], spec_cols: frozenset[str]) -> dict[str, Any]:
    """Return all columns not in the A1 spec as {col: value}."""
    return {k: v for k, v in raw.items() if k not in spec_cols and k}
