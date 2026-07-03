# PHASE3_EXECUTION_PLAN.md

> **Phase:** 3 — Import → Validation → Normalization  
> **Goal:** Turn a raw synthetic dataset into staged, validated, normalized registry candidates. Implements the first four ingestion stages of D-033 (Import → Validation → Normalization) up to — but excluding — deduplication and snapshot commit (Phase 4).  
> **Source of truth:** IMPLEMENTATION_ROADMAP.md (P3.1–P3.9), CLAUDE_CODE_HANDOFF.md §4/§6/§12, DECISIONS.md (D-003/D-004/D-005/D-008/D-017/D-018/D-019/D-024/D-040/D-042/D-046/D-047/D-049), PROJECT_CONTEXT.md §5/§7/§12.  
> **Prerequisite:** Phase 2 complete and reviewed (PHASE2_COMPLETION_REPORT.md ✅). Full schema migrated (`0001`–`0008`); all 5 seed scripts run. Audit contract `write_audit_entry` (P1.14) available.  
> **Phase 3 exit (per roadmap):** importing a synthetic CSV produces staged, validated, normalized candidate records — **not yet committed under a snapshot**.

---

## ⚠️ Required Decision Artifacts (READ FIRST — binding gate)

Phase 3 normalization and validation logic must be **deterministic and curator-controlled** (Golden Rule #3; D-024, D-045). Several tasks require deterministic rule sets whose *content* is a business decision, not an engineering choice. Per Golden Rule #1 — *"if a task seems to need something not decided, stop and ask; do not invent scope"* — **these artifacts must be authored and operator-approved before the sessions that consume them.** This plan **identifies where each is required and does not propose their content.**

| Artifact | Open question | Required before | Gate severity | Status |
|----------|---------------|-----------------|---------------|--------|
| **A1 — Import file-format spec** (CSV/XLSX column contract per source: LinkedIn / Verified / Tracer) | Q-010 note (build-time) | **S1** (P3.2 parser) | 🟡 REQUIRED | ❌ Not authored |
| **A2 — Curation API / OpenAPI outline** (import + validation + normalization endpoints) | Handoff §12 | **S2** (P3.3 entry points) | 🟡 REQUIRED | ❌ Not authored |
| **A3 — Geographic canonical list + remote/multi-location handling** | Q-009 | **S3** (P3.8 location) | 🟡 REQUIRED | ❌ Not authored |
| **A4 — Seniority ladder** (defined levels + deterministic title→level rules) | Q-007 | **S4** (P3.9 seniority) | 🔴 BLOCKER | ❌ Not authored |
| **A5 — Role/position normalization approach** (deterministic canonicalization of noisy titles) | Q-008 | **S4** (P3.9 role) | 🔴 BLOCKER | ❌ Not authored |
| **A6 — Program-name variant → canonical mapping** (deterministic variant table → 5 programs) | Q-005 | **S5** (P3.4 matcher) | 🔴 BLOCKER | ❌ Not authored |
| **A7 — Industry taxonomy standard** for `taxonomy_code` | Q-006 | **S3** (P3.7 industry) | 🟢 LOW (mitigated) | ⚠️ Partial — `seed_industry.py` already commits a custom taxonomy; `taxonomy_code` is nullable, so this does not block P3.7. |
| **A8 — Synthetic sample dataset** (minimal fixture exercising the pipeline; the full generator is P7.2) | Handoff §12 | **S1** onward (testing) | 🟢 LOW | ❌ Not authored — a minimal fixture suffices for Phase 3 tests. |

**Hard gate:** Sessions **S4** and **S5** must not begin until artifacts **A4, A5, A6** are approved. S1–S3 can proceed once A1–A3 are approved (A7/A8 are low-severity/mitigated). This document does **not** define A1–A8; it only marks their required-by points.

---

## Session Overview

| Session | ID | Roadmap Tasks | Type | Complexity | Requires artifacts |
|---------|----|--------------|------|-----------|--------------------|
| [S1](#session-s1--staging-schema--import-parser) | S1 | P3.1, P3.2 | DB + Backend | Heavy (M+L) | A1 (A8 for tests) |
| [S2](#session-s2--import-entry-points--audit-wiring) | S2 | P3.3 | Backend | Medium (M) | A2 |
| [S3](#session-s3--company--industry--location-normalization) | S3 | P3.6, P3.7, P3.8 | Backend | Heavy (L+M+M) | A3 (A7 mitigated) |
| [S4](#session-s4--role--seniority-assignment) | S4 | P3.9 | Backend | Medium (M) | **A4, A5 (blocking)** |
| [S5](#session-s5--programuniversity-matcher--validation-status) | S5 | P3.4, P3.5 | Backend | Heavy (L+M) | **A6 (blocking)** |
| [S6](#session-s6--phase-3-integration--review) | S6 | (integration/test/hardening) | Backend/Test | Medium (M) | — |

**Execution order:** S1 → S2 → then S3 / S4 / S5 are independent after S1 (roadmap parallelization note) but recommended S3 → S4 → S5 for solo focus → S6 last.  
**Dependency note (from roadmap):** company (P3.6) / location (P3.8) / role-seniority (P3.9) normalizers are independent after P3.2. P3.4→P3.5 depend on P3.2 + the STUDY_PROGRAM seed.

---

## Decision constraints (binding on every session)

- **D-033 / D-034:** Ingestion is a **manual import workflow** through FastAPI: Import → Validation → Normalization → Deduplication → Snapshot → Storage. Phase 3 covers the first three stages only. No real-time, no streaming.
- **D-002 / D-030 / D-045:** No AI/LLM/fuzzy matching anywhere. **All matching/validation/normalization is deterministic and curator-controlled** — lookup tables and explicit rules only.
- **D-024 / D-047:** Validation is curator-controlled; `validation_status ∈ {pending, validated, rejected}`; only `validated` enters analytics; non-matches route to `pending` (never silently dropped).
- **D-003 / D-004 / D-040:** Alumnus validity = university "Universitas Airlangga" **AND** program ∈ the 5 approved programs. University enforced in the validation workflow; stored as an attribute.
- **D-008 / D-017 / D-018 / D-042:** Company normalization via `COMPANY` + `COMPANY_ALIAS`; industry attached at **company** level with `industry_name` + `sector_name`.
- **D-019:** Geography normalized in `LOCATION` (country/province/city/region).
- **D-041 / D-046 / D-049:** `source_id` provenance NOT NULL on career records and set on alumni; trust tier is static, never computed, never auto-decides inclusion.
- **D-031 / D-036:** FastAPI is the single gateway; frontend never touches the DB; every mutation is audited (`write_audit_entry`, P1.14).
- **D-021 (boundary):** Phase 3 does **not** assign `snapshot_id` and does **not** commit under a snapshot — that is Phase 4 (P4.5). Leave `career_record.snapshot_id` NULL.
- **Golden rule:** if a task needs something not in DECISIONS.md D-001–D-051 (e.g. a seniority ladder), **stop and raise it** — do not invent scope. See the Required Decision Artifacts gate above.

---

## Session S1 — Staging Schema & Import Parser

### Roadmap tasks covered
- **P3.1** — Staging tables/models for raw imported rows (per source) with import-batch metadata.
- **P3.2** — Import parser service: accept CSV/XLSX per source (LinkedIn / Verified / Tracer), map to a common staging shape, record source + import batch.

### Objectives
1. Add a new Alembic migration (`0009`) introducing staging tables: an **import-batch** table (batch metadata: source, filename, row counts, status, timestamps, actor) and a **staging-row** table (raw parsed cells + a common normalized-candidate shape + FK to import batch + per-row status/error).
2. Implement SQLAlchemy models mirroring the migration.
3. Implement a deterministic import parser service that reads a CSV/XLSX for a declared source, maps columns to the common staging shape **per the approved file-format spec (A1)**, records the source and import batch, and writes staged rows with per-row parse status.
4. Unit-test the parser against minimal synthetic fixtures (A8): valid rows, malformed rows, missing-column handling, source-column mapping.

### Deliverables
- `migrations/versions/0009_staging_tables.py` — import-batch + staging-row tables
- `app/models/staging.py` — `ImportBatch`, `StagingRow` models
- `app/services/import_parser.py` — `parse_import(file, source, ...) -> ImportBatch` (deterministic column mapping)
- `app/schemas/imports.py` — Pydantic shapes for batch metadata + staged-row payloads
- `tests/test_import_parser.py` — parser unit tests (fixtures, no live DB)
- `tests/fixtures/` — minimal synthetic sample files per source (A8)

### Files expected to be created
```
backend/fastapi-app/migrations/versions/0009_staging_tables.py
backend/fastapi-app/app/models/staging.py
backend/fastapi-app/app/services/import_parser.py
backend/fastapi-app/app/schemas/imports.py
backend/fastapi-app/tests/test_import_parser.py
backend/fastapi-app/tests/fixtures/sample_linkedin.csv
backend/fastapi-app/tests/fixtures/sample_verified.csv
backend/fastapi-app/tests/fixtures/sample_tracer.csv
```

### Files expected to be modified
```
backend/fastapi-app/app/models/__init__.py     # register staging models for Alembic autogenerate / metadata
backend/fastapi-app/pyproject.toml              # add openpyxl (XLSX) + a CSV reader if not stdlib-only
```

### Dependencies
- **Phase 1 complete:** `CAREER_RECORD`, `CAPTURE_SOURCE` and all core tables migrated (P1.4, P1.11).
- **Artifact A1 (file-format spec)** approved — the parser's column mapping is defined by it. **Do not invent column contracts.**
- **Artifact A8 (synthetic fixtures)** — minimal sample files to test against.
- **S2 not required:** S1 produces the parser + staging; S2 wires entry points to it.

### Implementation notes
- Staging is **additive** schema work (migration `0009`); it does not alter any existing table. `StagingRow` should carry both the raw cells and the common candidate shape (name, program text, grad year, employer text, role text, location text, linkedin_url, source_id) so later normalizers (S3–S5) read from staging without re-parsing.
- `ImportBatch` records: `source_id`, `filename`, `total_rows`, `parsed_rows`, `error_rows`, `status`, `created_by` (nullable — CLI/system imports pre-date a request actor, consistent with `audit_log.changed_by` nullability), `created_at`.
- Parser is **pure and deterministic**: same file + same source ⇒ same staged rows. No inference, no fuzzy column detection — columns are resolved by the A1 spec.
- XLSX support via `openpyxl`; CSV via stdlib `csv`. Reject unknown source types with a clear error.
- **No audit wiring in S1** — that is S2 (P3.3). S1 stops at staged rows.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_import_parser.py
uv run pytest -v          # all Phase 1/2 tests (85) must still pass
uv run alembic upgrade head   # 0009 applies cleanly (against a local/transactional Postgres)
uv run alembic downgrade -1 ; uv run alembic upgrade head   # migration is reversible
```

### Acceptance criteria
1. Migration `0009` creates the import-batch and staging-row tables and is reversible (`downgrade` clean).
2. `parse_import` maps a source file to staged rows exactly per the A1 spec; deterministic for fixed input.
3. Malformed rows are recorded with a per-row error status — never silently dropped.
4. `ImportBatch` metadata (source, counts, status) is populated.
5. New parser tests pass; all 85 existing tests still pass; `ruff`/`black`/`mypy` clean.

### Estimated complexity
**Heavy (M + L).** New schema + a deterministic multi-source parser. Primary care: staging shape must be forward-compatible with S3–S5 normalizers and Phase 4 dedup (avoid rework, per readiness risk R-P3.7).

---

## Session S2 — Import Entry Points & Audit Wiring

### Roadmap tasks covered
- **P3.3** — Import entry points (resolves Q-027): admin-UI upload endpoint **and** `scripts/imports/` CLI, both writing to staging + audit (J).

### Objectives
1. Implement a FastAPI upload endpoint (`POST /imports`) that accepts a file + declared source, invokes the S1 parser, persists the import batch + staged rows, and writes an audit entry — guarded by `require_permission("import:run")`.
2. Implement a `scripts/imports/` CLI entry point that performs the same import against the DB from a local file (system/CLI context; `changed_by` NULL).
3. Verify import → staging → audit **atomicity** using the caller-owned-transaction contract of `write_audit_entry` (P1.14).
4. Test the endpoint (TestClient + dependency overrides + mocked/parser-stubbed service) and the CLI path.

### Deliverables
- `app/api/imports.py` — `POST /imports` (multipart upload; `import:run` guard)
- `scripts/imports/run_import.py` — CLI: `DATABASE_URL=... uv run python scripts/imports/run_import.py --source <s> --file <path>`
- `tests/test_imports_endpoint.py` — endpoint tests (guard, happy path, audit-write assertion)
- `tests/test_import_atomicity.py` — import + audit committed atomically (rollback on failure)

### Files expected to be created
```
backend/fastapi-app/app/api/imports.py
backend/fastapi-app/scripts_run_import_placeholder    # (see note) CLI lives under repo-root scripts/imports/
scripts/imports/run_import.py
backend/fastapi-app/tests/test_imports_endpoint.py
backend/fastapi-app/tests/test_import_atomicity.py
```
> Note: the CLI belongs in the repo-root `scripts/imports/` directory (established Phase 1), not inside the app package.

### Files expected to be modified
```
backend/fastapi-app/app/main.py               # include imports_router
backend/fastapi-app/app/api/__init__.py       # export imports_router
```

### Dependencies
- **S1 complete:** parser + staging models exist.
- **Artifact A2 (API/OpenAPI outline)** approved — the endpoint shape (path, request/response, error codes) follows it. **Do not invent endpoint contracts beyond A2.**
- **Phase 2 complete:** `require_permission("import:run")` guard and `get_current_user` available.
- **P1.14 audit contract:** `write_audit_entry` available.

### Implementation notes
- `POST /imports` uses FastAPI `UploadFile`; declares the source in the request; calls the S1 parser; within a single session transaction, persists the batch + staged rows **and** `write_audit_entry(session, table_name="import_batch", action_type="INSERT", ...)`, then commits — so audit and data commit together (D-025/D-031 pattern; this is the pipeline's first real use of the caller-owned-transaction contract, per readiness watch-item).
- The CLI performs the identical service call; `changed_by` is NULL (system context) — this is why `audit_log.changed_by` is nullable.
- **UI and CLI must have parity** (Q-027 resolution): both go through the same service function; the only difference is the actor and transport.
- Basic upload guardrails (file presence, declared-source validity) here; full size/type hardening is P7.8 — do not over-build.
- Do **not** run normalization or validation in this session — S2 stops at staged + audited rows.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_imports_endpoint.py tests/test_import_atomicity.py
uv run pytest -v          # all prior tests still pass
```
Manual (requires live Supabase + provisioned curator + backend running):
```
curl -X POST http://localhost:8000/imports \
  -H "Authorization: Bearer <curator-jwt>" \
  -F "source=LinkedIn" -F "file=@sample_linkedin.csv"
# Expected: 201 batch summary; AUDIT_LOG has a matching INSERT row.
# CLI:
DATABASE_URL=... uv run python scripts/imports/run_import.py --source LinkedIn --file sample_linkedin.csv
```

### Acceptance criteria
1. `POST /imports` behind `import:run`: non-curator/non-admin → 403.
2. Successful import persists batch + staged rows **and** one audit entry, atomically (both or neither).
3. CLI import produces identical staging output with `changed_by` NULL.
4. Parser failure rolls back the whole transaction (no orphan batch, no orphan audit).
5. All tests pass; `ruff`/`black`/`mypy` clean.

### Estimated complexity
**Medium (M).** Endpoint + CLI over the S1 service. Primary care: atomicity of the caller-owned audit transaction (first real consumer) and UI/CLI parity.

---

## Session S3 — Company, Industry & Location Normalization

### Roadmap tasks covered
- **P3.6** — Company normalization: resolve raw employer text → canonical `COMPANY` via `COMPANY_ALIAS`; create alias/company on first sight; centralized service (D-008/D-017).
- **P3.7** — Industry classification: attach company → `INDUSTRY` (industry_name/sector_name) at company level (D-018/D-042).
- **P3.8** — Location normalization: resolve raw location → `LOCATION` (country/province/city/region) (D-019); handle missing/remote.

### Objectives
1. Implement a centralized, deterministic company-normalization service: given a raw employer string from a staged row, resolve it to a canonical `COMPANY` via `COMPANY_ALIAS`; on first sight, create the alias (and the company if new), leaving `industry_id`/`location_id` NULL for later curator assignment (P4.10).
2. Implement industry attachment at the **company** level (not per career record), writing `industry_id` where deterministically resolvable; otherwise leave NULL for curator classification.
3. Implement deterministic location normalization mapping raw location text → `LOCATION`, handling missing/remote **per the approved geographic rules (A3)**.
4. Unit-test each normalizer for deterministic input→output and first-sight creation.

### Deliverables
- `app/services/company_normalization.py` — `resolve_company(raw_employer, source_id, session) -> Company`
- `app/services/industry_classification.py` — `attach_industry(company, ...) -> None` (company-level)
- `app/services/location_normalization.py` — `resolve_location(raw_location, session) -> Location | None`
- `tests/test_company_normalization.py`, `tests/test_industry_classification.py`, `tests/test_location_normalization.py`

### Files expected to be created
```
backend/fastapi-app/app/services/company_normalization.py
backend/fastapi-app/app/services/industry_classification.py
backend/fastapi-app/app/services/location_normalization.py
backend/fastapi-app/tests/test_company_normalization.py
backend/fastapi-app/tests/test_industry_classification.py
backend/fastapi-app/tests/test_location_normalization.py
```

### Files expected to be modified
```
(none expected — services are additive; staging models from S1 are read, not altered)
```

### Dependencies
- **S1 complete:** staged rows carry raw employer + raw location text.
- **P1.2 / P1.13:** `COMPANY`/`COMPANY_ALIAS` tables + `INDUSTRY`/`LOCATION` seeds exist.
- **Artifact A3 (geographic canonical list + remote/multi-location handling)** approved for P3.8. **Do not invent geographic canonicalization rules.**
- **Artifact A7 (industry taxonomy)** — *mitigated:* `seed_industry.py` already fixes the taxonomy and `taxonomy_code` is nullable, so P3.7 can attach by existing `industry_name`/`sector_name` without A7 being formally re-decided. If A7 is later authored, `taxonomy_code` can be backfilled — not a blocker.

### Implementation notes
- **Company (D-017):** the alias table is the deterministic index. `resolve_company` = lookup `COMPANY_ALIAS.alias_name == normalized(raw)`; if found → return its company; if not → create company (canonical_name = a deterministic canonicalization of the raw string) + alias row, `source_id` recorded. Normalization of the raw string must be deterministic (trim, collapse whitespace, case handling) — **no fuzzy matching**; curator later corrects/merges aliases (P4.10).
- **Industry (D-018/D-042):** attached at **company** level only. Where a deterministic mapping exists (e.g. curator-seeded association), set `company.industry_id`; otherwise leave NULL — the curator classifies in Phase 4. Never infer industry from noisy text with heuristics.
- **Location (D-019):** deterministic map raw → `LOCATION`; `country` is required on `LOCATION`, province/city/region nullable (partial resolution supported). "Remote"/missing handled per A3 (e.g. a sentinel or NULL policy defined there).
- These services are **centralized and reusable** (D-008 success metric: consistency). Later phases and the curator UI (P4.10) call the same functions.
- All three are **pure w.r.t. determinism**: fixed input ⇒ fixed output. Add tests asserting this explicitly (readiness risk R-P3.2).

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_company_normalization.py tests/test_industry_classification.py tests/test_location_normalization.py
uv run pytest -v          # all prior tests still pass
```

### Acceptance criteria
1. `resolve_company` returns the existing canonical company for a known alias and creates company+alias on first sight (with `source_id`).
2. New companies are created with `industry_id`/`location_id` NULL (curator-assignable later).
3. Industry attachment operates at company level only (never per career record).
4. `resolve_location` maps raw text to `LOCATION` deterministically and handles missing/remote per A3.
5. Each normalizer is deterministic (test: fixed input → fixed output). No fuzzy/AI logic.
6. All tests pass; `ruff`/`black`/`mypy` clean.

### Estimated complexity
**Heavy (L + M + M).** Company normalization is the L; industry and location are M. Primary care: deterministic canonicalization without drifting into fuzzy matching; correct first-sight creation semantics.

---

## Session S4 — Role & Seniority Assignment

### Roadmap tasks covered
- **P3.9** — Role & seniority assignment: store `role_title`; map to a defined seniority ladder deterministically (resolves build-time Q-007/Q-008).

### 🔴 Blocking prerequisite
**This session must not begin until artifacts A4 (seniority ladder) and A5 (role-normalization approach) are authored and operator-approved.** The roadmap task explicitly "resolves build-time Q-007/Q-008" — those decisions are the *input* to this code, not something to be invented here (Golden Rule #1). This plan identifies the requirement and stops; it does **not** propose a ladder or a role-canonicalization scheme.

### Objectives (pending A4/A5)
1. Store `role_title` on the career-record candidate from the staged row.
2. Map `role_title` → a seniority level **using the approved ladder (A4)** deterministically.
3. Canonicalize the role/position **using the approved approach (A5)** deterministically.
4. Unit-test the mapping for deterministic input→output across the ladder's defined levels.

### Deliverables (pending A4/A5)
- `app/services/role_seniority.py` — `assign_seniority(role_title) -> str` + role canonicalization, driven by the A4 ladder / A5 rules
- `tests/test_role_seniority.py` — deterministic mapping tests
- (If the ladder is stored as reference data rather than code constants, a small seed/reference artifact — **shape to be decided in A4**, not here.)

### Files expected to be created (pending A4/A5)
```
backend/fastapi-app/app/services/role_seniority.py
backend/fastapi-app/tests/test_role_seniority.py
```

### Files expected to be modified
```
(none expected — additive service reading staged rows; career_record.seniority is already nullable, assigned here)
```

### Dependencies
- **S1 complete:** staged rows carry raw role text.
- **🔴 Artifacts A4 (seniority ladder) + A5 (role normalization approach)** — **blocking.** No code in this session until both are approved.

### Implementation notes
- `career_record.seniority` is already nullable in Phase 1 precisely so P3.9 assigns it. The mapping must be a **lookup/rule table** (deterministic), not inference — consistent with D-045/Golden Rule #3.
- **No implementation is proposed here for the mapping content** because the ladder (A4) and canonicalization approach (A5) are undecided. When approved, the mapping becomes data-driven and testable with fixed input→output cases.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_role_seniority.py
uv run pytest -v          # all prior tests still pass
```

### Acceptance criteria (pending A4/A5)
1. `role_title` is stored verbatim on the candidate.
2. Seniority is assigned deterministically per the approved A4 ladder; unmapped titles get a defined default (per A4), never a guess.
3. Role canonicalization follows A5 deterministically.
4. Mapping is table/rule-driven with tests asserting determinism. No fuzzy/AI logic.
5. All tests pass; `ruff`/`black`/`mypy` clean.

### Estimated complexity
**Medium (M)** — once A4/A5 exist. The code is a deterministic lookup; the difficulty is entirely in the (external) decision, not the implementation.

---

## Session S5 — Program/University Matcher & Validation Status

### Roadmap tasks covered
- **P3.4** — Program/university matcher (deterministic): map staged program text → canonical `STUDY_PROGRAM`; flag university = UNAIR; no fuzzy/AI (D-040, D-024). Handles program-name variants (Q-005).
- **P3.5** — Validation-status assignment: set `pending`/`validated`/`rejected` per matcher outcome + curator gate; only valid program+university can become `validated` (D-047).

### 🔴 Blocking prerequisite
**P3.4 must not begin until artifact A6 (program-name variant → canonical mapping) is authored and operator-approved.** The task explicitly "handles program-name variants (Q-005)" deterministically — the variant table is the decision input, not something to invent (Golden Rule #1). This plan identifies the requirement and stops; it does **not** propose the variant mapping.

### Objectives (P3.4 pending A6; P3.5 ready)
1. Implement a deterministic program matcher: map staged program text → a canonical `STUDY_PROGRAM` **using the approved A6 variant table**; resolve to one of the 5 valid programs or the non-valid sentinel.
2. Deterministically flag `university == "Universitas Airlangga"` per D-040 (explicit string match; the value is stored as an attribute).
3. Implement validation-status assignment: set `pending` / `validated` / `rejected` per matcher outcome + curator gate — only a valid program **AND** UNAIR is eligible to become `validated`; non-matches route to `pending` (never dropped); explicit non-UNAIR / non-valid-program → `rejected` retained for audit/anti-churn (D-047).
4. Unit-test both: variant → canonical program (via A6), university flag, and the three-state assignment logic.

### Deliverables
- `app/services/program_matcher.py` — `match_program(raw_program) -> StudyProgram` + `is_unair(raw_university) -> bool` (P3.4; A6-driven)
- `app/services/validation_status.py` — `assign_validation_status(...) -> ValidationStatus` (P3.5)
- `tests/test_program_matcher.py`, `tests/test_validation_status.py`

### Files expected to be created
```
backend/fastapi-app/app/services/program_matcher.py
backend/fastapi-app/app/services/validation_status.py
backend/fastapi-app/tests/test_program_matcher.py
backend/fastapi-app/tests/test_validation_status.py
```

### Files expected to be modified
```
(none expected — additive services reading staged rows; alumni.validation_status is already enum-typed)
```

### Dependencies
- **S1 complete:** staged rows carry raw program + university text.
- **P1.10:** `STUDY_PROGRAM` seeded (5 valid + "Other / Unknown" sentinel).
- **🔴 Artifact A6 (program-variant mapping)** — **blocking for P3.4.** (P3.5's state logic can be built independently but is only meaningful once P3.4 feeds it.)

### Implementation notes
- **Matcher (D-024/D-040/D-044):** deterministic only. `match_program` resolves raw text via the A6 variant table to a canonical `STUDY_PROGRAM`; anything not explicitly mapped → the "Other / Unknown" sentinel (`is_ftmm_valid = false`). **No fuzzy/AI.**
- **University (D-040):** explicit match on "Universitas Airlangga"; stored as the `alumni.university` attribute; enforced in this validation workflow, not as a relational entity.
- **Validation states (D-047):** only (valid program `is_ftmm_valid = true`) **AND** (UNAIR) is `validated`-eligible — and the final `validated` transition is the **curator gate** (D-024), not automatic. Rows that fail the explicit match route to `pending` (curator review) or `rejected` (explicit non-match) — **never silently excluded** (readiness risk R-P3.3). `rejected` rows are retained (anti-churn).
- Boundary: **no dedup, no snapshot assignment** here — those are Phase 4 (P4.1–P4.5).

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_program_matcher.py tests/test_validation_status.py
uv run pytest -v          # all prior tests still pass
```

### Acceptance criteria
1. `match_program` maps every A6-listed variant to its canonical program; unmapped text → sentinel (`is_ftmm_valid=false`). Deterministic.
2. University flagged true only on explicit "Universitas Airlangga" match.
3. `validation_status` is `validated`-eligible only for valid program **AND** UNAIR, and the final `validated` state requires the curator gate.
4. Non-matches route to `pending`; explicit non-matches to `rejected`; nothing is silently dropped.
5. No fuzzy/AI logic anywhere. All tests pass; `ruff`/`black`/`mypy` clean.

### Estimated complexity
**Heavy (L + M)** — once A6 exists. The matcher is the L (variant handling + sentinel routing + state machine); status assignment is the M. Difficulty is concentrated in correct deterministic routing and the curator-gate boundary.

---

## Session S6 — Phase 3 Integration & Review

### Roadmap tasks covered
- (Integration / test consolidation / Phase 3 review — no new roadmap task; realizes the Phase 3 exit criterion end-to-end.)

### Objectives
1. Wire the S1–S5 services into a coherent post-import pipeline path so a single imported batch flows: staged → normalized (company/industry/location, role/seniority) → matched (program/university) → validation-status assigned — **stopping before dedup/snapshot** (Phase 4 boundary).
2. Add an integration test that imports a synthetic CSV and asserts staged, normalized, validated candidate output (no snapshot commit; `snapshot_id` NULL).
3. Run the full validator suite; produce `PHASE3_COMPLETION_REPORT.md`.

### Deliverables
- `app/services/ingestion_pipeline.py` — orchestrates S1–S5 services over a batch (Import→Validate→Normalize only)
- `tests/test_ingestion_pipeline.py` — end-to-end synthetic-CSV integration test
- `PHASE3_COMPLETION_REPORT.md` — completion report (tasks, acceptance, files, validation, tech debt, readiness for Phase 4)

### Files expected to be created
```
backend/fastapi-app/app/services/ingestion_pipeline.py
backend/fastapi-app/tests/test_ingestion_pipeline.py
PHASE3_COMPLETION_REPORT.md
```

### Files expected to be modified
```
backend/fastapi-app/app/api/imports.py     # optionally invoke the pipeline after staging (or keep staging-only + separate normalize step, per A2)
```

### Dependencies
- **S1–S5 complete** (and therefore artifacts A1–A6 approved).

### Implementation notes
- The orchestrator composes existing deterministic services; it introduces **no new business rules**.
- **Hard boundary check:** assert no `snapshot_id` is set and no dedup runs — those belong to Phase 4 (D-021, P4.1–P4.5). The Phase 3 exit is explicitly "not yet committed under a snapshot."
- Whether normalization runs inline with import or as a separate curator-triggered step is an **A2 (API outline)** decision — follow A2; do not invent the trigger surface.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v          # entire suite: Phase 1/2 + all Phase 3 tests green
```

### Acceptance criteria
1. Importing a synthetic CSV yields staged → normalized → validated candidate records.
2. `career_record.snapshot_id` remains NULL; no dedup executed (Phase 4 boundary respected).
3. Only valid-program + UNAIR rows are `validated`-eligible; others `pending`/`rejected`.
4. Every mutation path audited.
5. Full suite green; `ruff`/`black`/`mypy` clean; `PHASE3_COMPLETION_REPORT.md` produced.

### Estimated complexity
**Medium (M).** Composition + one integration test + report. No new business logic.

---

## Phase 3 Exit Criterion

Per IMPLEMENTATION_ROADMAP.md:

> *Importing a synthetic CSV produces staged, validated, normalized candidate records (not yet committed under a snapshot).*

Concrete verification:

1. `POST /imports` (curator JWT) or the CLI imports a synthetic CSV → an `ImportBatch` + staged rows + audit entry.
2. Employer text resolves to canonical `COMPANY` (via `COMPANY_ALIAS`); industry attached at company level where determinable; location normalized to `LOCATION`.
3. Role stored; seniority assigned per the approved ladder (A4).
4. Program text matched to a canonical `STUDY_PROGRAM` (via A6); university flagged; `validation_status` assigned (`pending`/`validated`-eligible/`rejected`).
5. **No `snapshot_id` assigned; no deduplication performed** (Phase 4 boundary).
6. All backend validators pass (`ruff`, `black`, `mypy`, `pytest`); migration `0009` reversible.

---

## Complexity Rollup

| Session | Tasks | Backend focus | Complexity | Blocking artifact |
|---------|-------|---------------|-----------|-------------------|
| S1 | P3.1, P3.2 | Staging schema + import parser | Heavy (M+L) | A1 (A8 tests) |
| S2 | P3.3 | Upload endpoint + CLI + audit atomicity | Medium (M) | A2 |
| S3 | P3.6, P3.7, P3.8 | Company + industry + location normalization | Heavy (L+M+M) | A3 (A7 mitigated) |
| S4 | P3.9 | Role + seniority assignment | Medium (M) | **A4, A5 🔴** |
| S5 | P3.4, P3.5 | Program/university matcher + validation status | Heavy (L+M) | **A6 🔴** |
| S6 | — | Integration + review + completion report | Medium (M) | — |

Phase 3 is one of the two heaviest phases (roadmap rollup: 4×M + 4×L). The engineering risk is concentrated in staging-shape forward-compatibility (S1) and deterministic-without-fuzzy discipline (S3–S5). **The critical-path risk is external:** S4 and S5 are gated on decision artifacts A4/A5/A6.

---

## New Package Dependencies

| Package | Side | Required by | Notes |
|---------|------|------------|-------|
| `openpyxl` | Backend | S1 | XLSX parsing for the import parser (P3.2). CSV uses stdlib `csv`. |

No new frontend packages — Phase 3 is backend-only (the curator UI that consumes these services is Phase 4, Epic P).

---

## Files Summary (all of Phase 3)

### Created
```
backend/fastapi-app/migrations/versions/0009_staging_tables.py
backend/fastapi-app/app/models/staging.py
backend/fastapi-app/app/schemas/imports.py
backend/fastapi-app/app/services/import_parser.py
backend/fastapi-app/app/services/company_normalization.py
backend/fastapi-app/app/services/industry_classification.py
backend/fastapi-app/app/services/location_normalization.py
backend/fastapi-app/app/services/role_seniority.py            # S4 — pending A4/A5
backend/fastapi-app/app/services/program_matcher.py           # S5 — pending A6
backend/fastapi-app/app/services/validation_status.py
backend/fastapi-app/app/services/ingestion_pipeline.py
backend/fastapi-app/app/api/imports.py
backend/fastapi-app/tests/test_import_parser.py
backend/fastapi-app/tests/test_imports_endpoint.py
backend/fastapi-app/tests/test_import_atomicity.py
backend/fastapi-app/tests/test_company_normalization.py
backend/fastapi-app/tests/test_industry_classification.py
backend/fastapi-app/tests/test_location_normalization.py
backend/fastapi-app/tests/test_role_seniority.py              # S4 — pending A4/A5
backend/fastapi-app/tests/test_program_matcher.py             # S5 — pending A6
backend/fastapi-app/tests/test_validation_status.py
backend/fastapi-app/tests/test_ingestion_pipeline.py
backend/fastapi-app/tests/fixtures/sample_linkedin.csv
backend/fastapi-app/tests/fixtures/sample_verified.csv
backend/fastapi-app/tests/fixtures/sample_tracer.csv
scripts/imports/run_import.py
PHASE3_COMPLETION_REPORT.md
```

### Modified
```
backend/fastapi-app/app/models/__init__.py     # register staging models
backend/fastapi-app/app/api/__init__.py         # export imports_router
backend/fastapi-app/app/main.py                 # include imports_router
backend/fastapi-app/pyproject.toml              # add openpyxl
```

### Not touched
```
backend/fastapi-app/app/models/alumni.py, career.py, company.py, reference.py, snapshot.py, security.py, audit.py
                                                # Phase 1 models — read-only in Phase 3 (fields already Phase-3-ready)
backend/fastapi-app/app/dependencies/          # Phase 2 auth/rbac — consumed, not modified
backend/fastapi-app/app/services/audit.py      # P1.14 contract — consumed, not modified
backend/fastapi-app/app/services/user_provisioning.py   # Phase 2 — not touched
frontend/                                       # no frontend work in Phase 3 (curator UI is Phase 4, Epic P)
migrations/versions/0001–0008                   # existing migrations — not altered
```

---

## Guardrails recap (execution agent)

- Build **strictly** to the roadmap task scope and DECISIONS.md. **Stop before dedup and snapshot** — those are Phase 4.
- **Do not author or invent** the content of decision artifacts A1–A8. Where a session requires one, **halt and request it** if it is not yet approved. S4/S5 are hard-gated on A4/A5/A6.
- All matching/validation/normalization is **deterministic** — lookup tables and explicit rules, never fuzzy/AI.
- Non-matches route to `pending` for curator review; nothing is silently dropped.
- Every mutation writes to `AUDIT_LOG` via `write_audit_entry`; the frontend never touches the DB.
- Synthetic data only (R-001/R-002). Leave `snapshot_id` NULL throughout Phase 3.
```
