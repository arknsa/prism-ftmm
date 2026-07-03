# Curator Runbook — Quarterly Alumni Data Refresh

> **Audience:** Data Curator role (has `import:run`, `alumni:validate`, `dedup:review`, `snapshot:manage` permissions).  
> **Frequency:** Once per quarter.  
> **Time estimate:** 30–60 minutes per quarter depending on dataset size and dedup volume.

---

## Overview

The dashboard displays analytics derived from **validated, snapshot-tagged career records**. Each quarter, a curator runs the following pipeline to add new data:

```
Collection → Snapshot → Import → Validate → Dedup Review → Commit → Verify
```

No step is irreversible. Rejected alumni are retained for audit. Dedup candidates can be re-reviewed.

---

## Prerequisites

- You must be logged in with the **Data Curator** role.
- The CSV/XLSX file must match the format in `docs/decisions/IMPORT_FILE_FORMAT_SPEC.md`.
- Required columns: `full_name`, `study_program`, `graduation_year`  
  Optional columns: `employer`, `role_title`, `location`, `linkedin_url`
- File size limit: 10 MB.
- `study_program` must match one of the 5 approved FTMM programs (or a recognized variant — see `docs/decisions/PROGRAM_VARIANT_MAP_SPEC.md`).

---

## Step 1: Create the Quarterly Snapshot

A **snapshot** is a named time-point that career records are tagged to. Create one per quarter before importing.

**Via UI:** `Curator → Snapshots → New Snapshot`  
**Via API:**
```http
POST /api/v1/snapshots
Content-Type: application/json

{
  "quarter_label": "2025-Q3",
  "notes": "Tracer Study annual batch"
}
```

**Rules (D-021):**
- `quarter_label` format: `YYYY-Q[1-4]` (e.g., `2025-Q3`).
- Each label must be unique. Creating a duplicate returns HTTP 400.
- The `refresh_date` defaults to today.

Note the `snapshot_id` returned — you will reference it in Step 4.

---

## Step 2: Import the Source File

Upload the quarterly CSV/XLSX through the import UI or API.

**Via UI:** `Curator → Import → Upload File`  
Select `source_type` (Tracer Study / LinkedIn / Verified Faculty Record), attach the file, submit.

**Via API:**
```http
POST /api/v1/imports
Content-Type: multipart/form-data

file:        <your CSV/XLSX>
source_type: "Tracer Study"
source_id:   <capture_source_id for the tracer study record>
```

**What happens:**
- Each row is parsed and staged as a `StagingRow` with `row_status = "pending"` or `"error"`.
- The batch is returned immediately with `batch_id`, `total_rows`, `parsed_rows`, `error_rows`.
- No alumni or career records are created yet.

**Check for parse errors:**
```http
GET /api/v1/imports/{batch_id}/rows?status=error
```
Review and fix any errors in the source file, then re-upload if needed.

---

## Step 3: Review Staged Rows

Before committing, inspect the staged rows to spot issues.

```http
GET /api/v1/imports/{batch_id}/rows?page=1&page_size=50
```

Common issues to look for:
- `row_status = "error"` — column missing or unparseable graduation year.
- Unrecognized `study_program` values — these are mapped via `PROGRAM_VARIANT_MAP_SPEC.md`; unmatched values produce error rows.
- Blank `employer` field — alumni without a current employer will be committed without a career record (reported as "Not Reported" in analytics, per D-048).

---

## Step 4: Commit the Batch

Commit assigns each staged row to a snapshot and creates/updates Alumni and CareerRecord rows.

**Via UI:** `Curator → Import → View Batch → Commit to Snapshot`  
**Via API:**
```http
POST /api/v1/commit
Content-Type: application/json

{
  "batch_id": 10,
  "snapshot_id": 3
}
```

**What happens per row (D-044, D-045):**
1. **Program match:** `study_program` is matched to one of the 5 approved FTMM programs.
2. **Company normalization:** `employer` is resolved to a canonical `Company` (or a new one is created).
3. **Dedup Tier 1:** If `linkedin_url` matches an existing alumni → auto-link (outcome: `linked`).
4. **Dedup Tier 2:** If `full_name + study_program + graduation_year` matches → added to dedup queue (outcome: `pending_dedup`). **See Step 5.**
5. **New alumni:** No match → new `Alumni` row with `validation_status = pending`.
6. **Career record:** If employer resolved → new `CareerRecord` with `is_current = True` and `snapshot_id` tagged. Previous `is_current` records are cleared (D-020).

**Response includes:**
```json
{
  "total": 100,
  "created": 78,
  "linked": 15,
  "pending_dedup": 7,
  "skipped_error": 0
}
```

**Important:** `pending_dedup` rows need curator action before they become visible in analytics. Proceed to Step 5 if non-zero.

---

## Step 5: Review Dedup Candidates (if any)

When the commit finds a Tier-2 candidate match (same name + program + year), a `DedupCandidate` is created for curator review.

**Via UI:** `Curator → Dedup Review`  
**Via API:**
```http
GET /api/v1/dedup/candidates
```

For each candidate, choose one of two resolutions:

| Resolution | Meaning |
|---|---|
| `merge` | The new row belongs to the existing alumni — link the career record to them. |
| `keep_separate` | These are different people — create a new alumni record. |

```http
POST /api/v1/dedup/candidates/{id}/resolve
Content-Type: application/json

{ "resolution": "merge" }
```

After resolving, re-run the commit for the batch to process the previously-blocked rows.

---

## Step 6: Validate Alumni (D-024, D-047)

**This is the critical gate.** Only alumni with `validation_status = validated` appear in analytics.

The commit pipeline deliberately leaves new alumni as `pending`. The curator must explicitly validate them after reviewing the data for correctness.

**Via UI:** `Curator → Validation Queue`  
Shows all pending alumni with their imported data.

**Via API — validate a single alumnus:**
```http
POST /api/v1/alumni/{alumni_id}/validate
Content-Type: application/json

{ "action": "validate" }
```

**To reject (retains record for audit, excludes from analytics):**
```http
POST /api/v1/alumni/{alumni_id}/validate
Content-Type: application/json

{ "action": "reject", "reason": "Not an FTMM program graduate" }
```

**Validation rules (D-003, D-047):**
- Alumni must have a valid FTMM study program.
- Must have "Universitas Airlangga" as their university (enforced at import; verify if uncertain).
- Rejected alumni are stored permanently for anti-churn and audit purposes.

**Tip for large batches:** Use `GET /api/v1/alumni?validation_status=pending` to list all pending alumni and validate in bulk via the curator UI.

---

## Step 7: Verify Analytics

After validation, open the dashboard to confirm the new data is visible.

1. **Overview page** — check `Total Alumni` count increased as expected.
2. **Filter by snapshot** — select the new quarter to see this cohort's data in isolation.
3. **Career Outcomes page** — verify "Employed vs Not Reported" split is reasonable.
4. **Company / Industry / Geography pages** — spot-check top employers and countries.
5. **Alumni Directory** — search for specific alumni from the new import to confirm their records.

The analytics always show **validated alumni only** (D-047). Alumni still in `pending` status do not appear.

---

## Quarterly Checklist

```
□ Snapshot created with correct quarter_label (YYYY-Q[1-4])
□ Source file uploaded and parsed (check error_rows = 0 or acceptable)
□ Staged rows reviewed for data quality
□ Batch committed to snapshot
□ Dedup candidates resolved (if any pending_dedup rows)
□ All new alumni validated (or intentionally rejected)
□ Analytics overview shows expected new count
□ Carry-forward alumni still visible with updated career records
```

---

## Carry-Forward Alumni (between quarters)

Alumni from previous quarters automatically appear in the new quarter's data when:
- Their `linkedin_url` matches a row in the new CSV (Tier-1 auto-link), **or**
- Their `full_name + study_program + graduation_year` matches and the curator resolves the dedup candidate as `merge` (Tier-2 link).

A linked alumni receives a new `CareerRecord` for the new snapshot. Their previous career record has `is_current` set to `False`. The analytics show only the **most recent** career record as their current role.

---

## Error Reference

| Error | Cause | Fix |
|---|---|---|
| HTTP 400 on import | Unsupported `source_type` | Use `"Tracer Study"`, `"LinkedIn"`, or `"Verified Faculty Record"` |
| HTTP 413 on import | File exceeds 10 MB | Split the file into smaller batches |
| HTTP 400 on import (CSV parse error) | Malformed CSV field | Fix the source file encoding or field delimiters |
| HTTP 400 on snapshot | `quarter_label` already exists | A snapshot for that quarter already exists — proceed to import |
| HTTP 400 on snapshot | Invalid `quarter_label` format | Must be `YYYY-Q[1-4]` (e.g., `2025-Q3`, not `Q3-2025`) |
| HTTP 403 | Missing permission | Ensure your account has the Data Curator role |
| HTTP 404 on commit | `batch_id` or `snapshot_id` not found | Verify IDs from import/snapshot responses |

---

## Rollback (if needed)

There is no automated rollback. If incorrect data was committed and validated:

1. Use `POST /api/v1/alumni/{id}/validate` with `action: "reject"` to exclude specific alumni from analytics.
2. To correct company/role data, contact the system administrator to update records directly.
3. A future data import for the next quarter can carry-forward corrected data via Tier-1/Tier-2 dedup resolution.

Audit log entries for all actions are permanent (D-025).

---

## Synthetic Data (Development / Demo)

For development and demo purposes, use the pre-generated synthetic dataset:

```bash
# Generate fresh synthetic data (reproducible)
python scripts/maintenance/generate_synthetic_data.py --output-dir data/synthetic --seed 42
```

This creates:
- `data/synthetic/synthetic_alumni_2025_Q1.csv` — 100 alumni, Q1 snapshot
- `data/synthetic/synthetic_alumni_2025_Q2.csv` — 120 alumni (100 carry-forward + 20 new grads), Q2 snapshot

Seed these through the normal import pipeline to populate the demo environment:
1. Create snapshot `2025-Q1`
2. Import Q1 CSV via `Tracer Study` source
3. Validate all alumni
4. Create snapshot `2025-Q2`
5. Import Q2 CSV
6. Validate new alumni (alumni_id > 100)

All names, URLs, and employer data in synthetic files are fabricated — no real PII (D-050, D-051).
