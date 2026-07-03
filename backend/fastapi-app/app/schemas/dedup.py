"""Pydantic schemas for the dedup curator review queue (P4.3)."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class DedupCandidateOut(BaseModel):
    """Output schema for a single dedup candidate queue entry."""

    model_config = ConfigDict(from_attributes=True)

    dedup_candidate_id: int
    staging_row_id: int
    matched_alumni_id: int
    resolution: str
    resolved_by: int | None
    resolved_at: datetime.datetime | None
    created_at: datetime.datetime


class DedupCandidateListOut(BaseModel):
    """Paginated list of dedup candidates."""

    total: int
    items: list[DedupCandidateOut]


class DedupResolveIn(BaseModel):
    """Request body for resolving a dedup candidate."""

    resolution: str  # "merge" or "keep_separate"
