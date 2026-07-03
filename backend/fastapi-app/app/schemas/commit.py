"""Pydantic schemas for the commit/storage stage (P4.5)."""

from __future__ import annotations

from pydantic import BaseModel


class CommitRowResultOut(BaseModel):
    """Result of committing a single StagingRow."""

    staging_row_id: int
    outcome: str
    alumni_id: int | None = None
    career_record_id: int | None = None
    detail: str = ""
    dedup_candidate_ids: list[int] = []


class CommitBatchResultOut(BaseModel):
    """Aggregated result of committing all rows in a batch."""

    batch_id: int
    snapshot_id: int
    total: int
    created: int
    linked: int
    pending_dedup: int
    skipped_error: int
    skipped_no_employer: int
    rows: list[CommitRowResultOut]


class CommitBatchIn(BaseModel):
    """Request body to trigger a batch commit."""

    batch_id: int
    snapshot_id: int


class ValidateAlumniIn(BaseModel):
    """Request body to validate or reject an alumni record (D-024 curator gate)."""

    action: str
    reason: str | None = None
