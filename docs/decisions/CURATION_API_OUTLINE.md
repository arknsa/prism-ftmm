# CURATION_API_OUTLINE.md — Artifact A2

> **Status:** Approved  
> **Required by:** Phase 3, Session S2 (P3.3 import entry points)  
> **Resolves:** CLAUDE_CODE_HANDOFF.md §12 ("Before Phases 3/5: API contract / OpenAPI outline for curation + aggregation endpoints")  
> **Scope:** Import and validation endpoints only. Aggregation endpoints are Phase 5 (P5.1–P5.8).  
> **Decisions:** D-031 (FastAPI gateway), D-033 (manual import workflow), D-025 (audit), D-036 (RBAC), D-047 (validation states).  
> **Last updated:** 2026-07-01

---

## Design Constraints (non-negotiable)

- **FastAPI is the single gateway** (D-031). Frontend never calls DB directly.
- **All mutations write to `AUDIT_LOG`** via `write_audit_entry` (D-025, P1.14). Audit and data commit atomically (caller-owned transaction pattern).
- **RBAC enforced on every endpoint** via `require_permission` (D-036).
- **Phase 3 endpoints stop before dedup and snapshot commit** (D-021 boundary). No `snapshot_id` assigned here.
- **Deterministic only.** No inference, no fuzzy matching, no AI (D-002, D-030).

---

## Base URL Convention

All Phase 3/4 curation endpoints are prefixed `/api/v1`. The Phase 2 `/me` and `/users` endpoints use the same prefix convention.

---

## Phase 3 Endpoints

### EP-1 — `POST /api/v1/imports`

**Purpose:** Accept a file upload for a declared source, run the import parser (P3.2), persist the import batch + staged rows, and write an audit entry — all atomically.

**Permission:** `import:run` (Admin + Data Curator)

**Request:** `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | `UploadFile` | ✓ | `.csv` or `.xlsx` only |
| `source_type` | `str` (form field) | ✓ | One of: `"LinkedIn"`, `"Verified Faculty Record"`, `"Tracer Study"` |
| `source_id` | `int` (form field) | ✓ | FK to `CAPTURE_SOURCE.source_id` (caller resolves mapping) |

**Success response:** `HTTP 201 Created`

```json
{
  "batch_id": 42,
  "source_id": 3,
  "filename": "alumni_linkedin_q1.csv",
  "total_rows": 150,
  "parsed_rows": 148,
  "error_rows": 2,
  "status": "complete",
  "created_by": 7,
  "created_at": "2026-07-01T10:00:00Z"
}
```
Schema: `BatchSummary` (already defined in `app/schemas/imports.py`).

**Error responses:**

| HTTP | Condition |
|------|-----------|
| 400 | Unknown `source_type` or unsupported file extension |
| 401 | Missing / invalid JWT |
| 403 | Authenticated user lacks `import:run` permission |
| 422 | Missing required form fields |

**Atomicity contract:** Within a single session, in order:
1. Call `parse_import(...)` which flushes the batch (to get `batch_id`) and adds staging rows.
2. Call `write_audit_entry(session, table_name="import_batch", record_id=str(batch_id), action_type="INSERT", new_values={batch metadata}, changed_by=user.user_id)`.
3. `session.commit()` — data + audit land together.
4. On any exception before commit: `session.rollback()` — no orphan batch, no orphan audit entry.

**CLI parity:** The same `parse_import` service call is used by the CLI (`scripts/imports/run_import.py`). The only differences: `changed_by = None` (system context), and transport is CLI args rather than HTTP.

---

### EP-2 — `GET /api/v1/imports/{batch_id}`

**Purpose:** Retrieve summary of a completed import batch (for the admin UI import screen, Phase 4 P4.7).

**Permission:** `import:run` (Admin + Data Curator)

**Path parameter:** `batch_id: int`

**Success response:** `HTTP 200 OK`  
Schema: `BatchSummary`

**Error responses:**

| HTTP | Condition |
|------|-----------|
| 401 | Missing / invalid JWT |
| 403 | Insufficient permission |
| 404 | Batch not found |

---

### EP-3 — `GET /api/v1/imports/{batch_id}/rows`

**Purpose:** Paginated list of staged rows for a batch — used by the import screen to show per-row parse errors.

**Permission:** `import:run`

**Query parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `status` | `str` | (all) | Filter by `row_status`: `"pending"`, `"error"`, or omit for all |
| `page` | `int` | `1` | 1-indexed page number |
| `page_size` | `int` | `50` | Max 200 |

**Success response:** `HTTP 200 OK`

```json
{
  "batch_id": 42,
  "total": 150,
  "page": 1,
  "page_size": 50,
  "items": [ /* array of StagingRowOut */ ]
}
```

**Error responses:** same pattern as EP-2.

---

## Endpoint Router Registration

- File: `backend/fastapi-app/app/api/imports.py`
- Router prefix: `/api/v1/imports`
- Tags: `["imports"]`
- Registered in `app/main.py` as `app.include_router(imports_router)`

---

## CLI Entry Point

- File: `scripts/imports/run_import.py`
- Invocation: `DATABASE_URL=... uv run python scripts/imports/run_import.py --source <source_type> --source-id <int> --file <path>`
- `changed_by`: always `None` (no request context; system import).
- Exit codes: `0` success, `1` parse/validation error, `2` DB/config error.
- Outputs a text summary of the batch result to stdout.

---

## Normalization Trigger Policy (S2 boundary)

S2 implements **staging only** — the import endpoint stages rows and audits the batch. It does **not** trigger normalization (S3), program matching (S5), or validation-status assignment (S5). Those are separate, curator-triggered steps.

The Phase 3 orchestration (S6: `ingestion_pipeline.py`) wires these services sequentially; at S2, the import endpoint stops after `session.commit()` on the batch.

---

## Not in Scope (Phase 3 / S2)

- Validation status endpoints (Validation screen — Phase 4 P4.8 curl).
- Dedup endpoints (Phase 4 P4.3).
- Company-alias management (Phase 4 P4.10).
- Snapshot control (Phase 4 P4.11).
- Aggregation / filter endpoints (Phase 5).
