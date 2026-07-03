"""Import pipeline entry point — POST /api/v1/imports (P3.3).

Implements EP-1, EP-2, EP-3 from Artifact A2 (CURATION_API_OUTLINE.md).

POST /api/v1/imports    — upload a CSV/XLSX, stage all rows, write audit entry.
GET  /api/v1/imports/{batch_id}         — batch summary.
GET  /api/v1/imports/{batch_id}/rows    — paginated staged rows.

Atomicity contract (A2 §EP-1, D-025, D-031):
  parse_import → flush (batch_id) → add staging rows → write_audit_entry → commit.
  Any exception triggers rollback; no orphan batch or audit entry is ever written.

Normalization is NOT triggered here (S2 boundary per A2). Staging stops after commit.

Decisions: D-031 (gateway), D-033 (manual import), D-025 (audit), D-036 (RBAC).
"""

from __future__ import annotations

import csv as _csv_module
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.models.staging import ImportBatch, StagingRow
from app.rate_limiting import import_rate_limit
from app.schemas.auth import AuthenticatedUser
from app.schemas.imports import BatchSummary, PagedStagingRows, StagingRowOut
from app.services.audit import write_audit_entry
from app.services.import_parser import SUPPORTED_SOURCES, parse_import

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


# ---------------------------------------------------------------------------
# EP-1 — POST /api/v1/imports
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=BatchSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a source file and stage all rows",
)
def run_import(
    file: UploadFile,
    source_type: Annotated[str, Form()],
    source_id: Annotated[int, Form()],
    _rl: None = Depends(import_rate_limit),
    user: AuthenticatedUser = Depends(require_permission("import:run")),
    session: Session = Depends(get_session),
) -> BatchSummary:
    """Accept a CSV/XLSX upload, parse and stage all rows, write audit entry.

    Validates ``source_type`` and file extension before parsing. On success
    returns ``HTTP 201`` with the batch summary. On any error the transaction
    is rolled back — no orphan batch or audit row is ever committed.

    Permission required: ``import:run`` (Admin, Data Curator).
    """
    if source_type not in SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown source_type {source_type!r}. " f"Supported: {sorted(SUPPORTED_SOURCES)}"
            ),
        )

    filename = file.filename or "upload"

    # Size guard: reject uploads exceeding 10 MB to prevent memory exhaustion.
    # Synthetic/tracer-study datasets for 100–5 000 alumni are well under this.
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
    content = file.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload exceeds the {_MAX_UPLOAD_BYTES // (1024*1024)} MB limit.",
        )

    try:
        batch = parse_import(
            file_content=content,
            filename=filename,
            source_type=source_type,
            source_id=source_id,
            session=session,
            created_by=user.user_id,
        )

        write_audit_entry(
            session,
            table_name="import_batch",
            record_id=str(batch.batch_id),
            action_type="INSERT",
            new_values=_batch_to_dict(batch),
            changed_by=user.user_id,
        )

        session.commit()

    except (ValueError, UnicodeDecodeError, _csv_module.Error) as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        session.rollback()
        logger.exception("Unexpected error during import; transaction rolled back.")
        raise

    logger.info(
        "import completed: batch_id=%s source=%r filename=%r total=%d errors=%d actor=%s",
        batch.batch_id,
        source_type,
        filename,
        batch.total_rows,
        batch.error_rows,
        user.user_id,
    )
    return BatchSummary.model_validate(batch)


# ---------------------------------------------------------------------------
# EP-2 — GET /api/v1/imports/{batch_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{batch_id}",
    response_model=BatchSummary,
    summary="Retrieve import batch summary",
)
def get_batch(
    batch_id: int,
    _user: AuthenticatedUser = Depends(require_permission("import:run")),
    session: Session = Depends(get_session),
) -> BatchSummary:
    """Return metadata for a single import batch.

    Permission required: ``import:run``.
    """
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
    return BatchSummary.model_validate(batch)


# ---------------------------------------------------------------------------
# EP-3 — GET /api/v1/imports/{batch_id}/rows
# ---------------------------------------------------------------------------


@router.get(
    "/{batch_id}/rows",
    response_model=PagedStagingRows,
    summary="Paginated staged rows for an import batch",
)
def get_batch_rows(
    batch_id: int,
    row_status: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    _user: AuthenticatedUser = Depends(require_permission("import:run")),
    session: Session = Depends(get_session),
) -> PagedStagingRows:
    """Return a paginated list of staged rows for a batch.

    Optionally filter by ``status`` (``"pending"`` or ``"error"``).
    Permission required: ``import:run``.
    """
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")

    base_stmt = select(StagingRow).where(StagingRow.batch_id == batch_id)
    count_stmt = select(func.count()).select_from(StagingRow).where(StagingRow.batch_id == batch_id)

    if row_status is not None:
        base_stmt = base_stmt.where(StagingRow.row_status == row_status)
        count_stmt = count_stmt.where(StagingRow.row_status == row_status)

    total = session.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    rows = session.scalars(
        base_stmt.order_by(StagingRow.row_number).offset(offset).limit(page_size)
    ).all()

    return PagedStagingRows(
        batch_id=batch_id,
        total=total,
        page=page,
        page_size=page_size,
        items=[StagingRowOut.model_validate(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _batch_to_dict(batch: ImportBatch) -> dict[str, Any]:
    return {
        "batch_id": batch.batch_id,
        "source_id": batch.source_id,
        "filename": batch.filename,
        "total_rows": batch.total_rows,
        "parsed_rows": batch.parsed_rows,
        "error_rows": batch.error_rows,
        "status": batch.status,
        "created_by": batch.created_by,
    }
