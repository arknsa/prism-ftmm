"""Pydantic schemas for the Phase 3 import pipeline (P3.1 / P3.2 / P3.3).

BatchSummary:    returned from parse_import(); describes an ImportBatch.
StagingRowOut:   describes one StagingRow for API/test inspection.
PagedStagingRows: paginated EP-3 response (A2 §EP-3).

Decisions: D-033 (manual import workflow), D-031 (FastAPI gateway).
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StagingRowOut(BaseModel):
    """Read-only view of one staged row."""

    model_config = ConfigDict(from_attributes=True)

    staging_row_id: int
    batch_id: int
    row_number: int
    raw_full_name: str | None
    raw_study_program: str | None
    raw_graduation_year: int | None
    raw_employer: str | None
    raw_role_title: str | None
    raw_location: str | None
    raw_linkedin_url: str | None
    raw_extra: dict[str, Any] | None
    row_status: str
    row_error: str | None
    created_at: datetime.datetime


class BatchSummary(BaseModel):
    """Summary of an import batch — returned from parse_import()."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: int
    source_id: int
    filename: str
    total_rows: int
    parsed_rows: int
    error_rows: int
    status: str
    created_by: int | None
    created_at: datetime.datetime


class PagedStagingRows(BaseModel):
    """Paginated list of staged rows for EP-3 (A2 §EP-3)."""

    batch_id: int
    total: int
    page: int
    page_size: int
    items: list[StagingRowOut]


class PagedImportBatches(BaseModel):
    """Paginated list of import batches (batch history)."""

    total: int
    page: int
    page_size: int
    items: list[BatchSummary]
