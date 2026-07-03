"""Pydantic schemas for snapshot management (P4.4, P4.11)."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class SnapshotOut(BaseModel):
    """Output schema for a single REFRESH_SNAPSHOT."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    quarter_label: str
    refresh_date: datetime.date
    notes: str | None
    created_at: datetime.datetime


class SnapshotListOut(BaseModel):
    """List of snapshots."""

    total: int
    items: list[SnapshotOut]


class SnapshotCreateIn(BaseModel):
    """Request body for opening a new snapshot quarter."""

    quarter_label: str
    refresh_date: datetime.date | None = None
    notes: str | None = None
