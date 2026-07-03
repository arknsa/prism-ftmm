# Next Session Handoff

**Prepared:** 2026-07-02  
**Last completed:** Phase 5–6 (complete), P7.1–P7.2, P7.4, P7.6–P7.8 complete; P7.7 frontend tests complete; repo-wide engineering audit complete; production readiness review complete  
**Next milestone:** P7.3 / P7.5 / P7.9 all blocked on cloud accounts (Supabase/Railway/Vercel)

> **Audit note (2026-07-02):** A repository-wide audit fixed one correctness bug — the
> `country` filter was silently ignored by Overview / Career Outcomes / Companies / Industries
> (only Geography + Directory applied it). Now centralized via `build_country_clause` and
> applied consistently. One dead helper (`filters_need_company_join`) removed. Stale Phase-0
> docs refreshed. See `FINAL_ENGINEERING_AUDIT.md` for the full report.

> **Production readiness note (2026-07-02):** Four hardening fixes applied — OpenAPI docs now
> disabled in production (`APP_ENV=production`), log level configurable via `LOG_LEVEL` env
> var, HTTP security headers added to `next.config.ts`, and `railway.toml` created so Railway
> runs `alembic upgrade head` before starting uvicorn. See `PRODUCTION_READINESS_REPORT.md`.

---

## What Was Completed This Session

### P7.1 — E2E Quarterly Refresh Tests + Curator Runbook
- **`tests/test_quarterly_e2e.py`** — 29 tests covering the full two-quarter pipeline via FastAPI TestClient:
  - `TestSnapshotCreationStage` — D-021 (unique label), 403 guard, audit wiring
  - `TestImportStage` — import → batch summary, Q1 (3 rows) and Q2 (120 rows)
  - `TestCommitStage` — Q1 creates alumni, Q2 links existing + creates new, D-031 (API owns commit), D-047 (never auto-validated)
  - `TestValidationGate` — D-024 (curator only), D-025 (audit entry), reject → retained for audit
  - `TestAnalyticsReflectValidatedCohort` — D-047 (only validated appear), D-048 (no unemployment rate field)
  - `TestPointInTimeCorrectness` — D-007 snapshot filter propagated, Q1 vs Q2 isolation
  - `TestTwoQuarterOrchestration` — full Q1 + Q2 golden path including carry-forward and point-in-time
- **`docs/CURATOR_RUNBOOK.md`** — step-by-step guide for quarterly refresh:
  - Steps 1–7: Create Snapshot → Import → Review Staged → Commit → Dedup Review → Validate → Verify Analytics
  - Quarterly checklist, error reference table, carry-forward explanation, synthetic data section

### P7.4 — Documentation Set
- **`docs/CURATOR_RUNBOOK.md`** — complete (see above)
- **`README.md`** — updated from stale Phase 0 description to current MVP state:
  - Features section (Data Curation Pipeline + Analytics Dashboard + Security/RBAC table)
  - Complete monorepo layout with all current paths
  - Phase status table (P0–P6 complete, P7 in progress)
  - Updated governance docs links (added curator runbook, ER diagram, NEXT_SESSION_HANDOFF)
  - Quality gates section

### P7.6 — Backend Test Hardening
- **`tests/test_aggregation_edge_cases.py`** — 31 new tests:
  - `TestEmptyDataset` — all 6 analytics endpoints return 200 with zeros/empty lists when no validated alumni exist
  - `TestSingleAlumnus` — boundary: single alumnus, all employed, none employed
  - `TestD048ArithmeticBoundaries` — 8 parametrized combinations (0,0,0 → 100,100,0 → all not_reported)
  - Response never exposes `unemployment_rate`, `unemployed_count`, `unemployed`
  - `TestD047FilterGuard` — always includes validated guard in WHERE clauses
  - `TestImportParserBoundaries` — header-only CSV, single row, all-error rows, mixed valid/error, Unicode names, blank employer (D-048 "Not Reported")
  - `TestFilterDimensionPropagation` — country filter and all 6 filter dimensions propagate correctly

### P7.7 — Frontend Tests (vitest + @testing-library/react)

**Test stack installed:**
- `vitest ^4.1.9` + `@vitejs/plugin-react ^6.0.3` + `happy-dom ^20.10.6` + `@testing-library/react ^16.3.2`
- `vitest.config.ts` — happy-dom environment, `@/` alias matching tsconfig paths, `__tests__/**` glob

**Test files (4 files, 23 tests total):**

| File | Tests | What it covers |
|------|-------|---------------|
| `__tests__/lib/build-query-string.test.ts` | 6 | `buildQueryString` — empty, single, multi, URL-encoding, empty-value filtering |
| `__tests__/lib/api-client.test.ts` | 8 | `ApiError` (3 assertions) + `apiFetch`: network failure, backend detail propagation, generic fallback, success, auth header |
| `__tests__/lib/filter-context.test.tsx` | 6 | `FilterProvider` / `useFilters`: initial state, `setFilter`, `toQueryParams`, null omission, `clearFilters` |
| `__tests__/lib/auth-context.test.tsx` | 3 | `AuthProvider`: 401 → signOut + redirect to /login, success → user set, 500 → no redirect |

**Key technical notes:**
- `vi.hoisted()` required for mock refs used in `vi.mock()` factories (vitest 4.x hoists mock calls above imports)
- `vi.spyOn(console, "error").mockImplementation(() => {})` at module scope — suppresses auth-context's console.error from racing with happy-dom's async log RPC during teardown
- Probe component captures state via `useEffect` (not during render) to satisfy ESLint `react-hooks/globals` rule
- `globals: false` in vitest config — all vitest APIs (`describe`, `it`, `vi`, `expect`, `afterEach`, etc.) must be explicitly imported

**`pnpm test` command:** `vitest run` (single-pass, CI-ready)

### P7.2 — Synthetic Data Generator
- **`scripts/maintenance/generate_synthetic_data.py`** — reproducible synthetic CSV generator:
  - Produces `data/synthetic/synthetic_alumni_2025_Q1.csv` (100 alumni) and `..._Q2.csv` (120 alumni — carry-forward + 20 new grads)
  - Seeded (`--seed 42`) for reproducibility; all names/URLs/employers are fabricated (D-050, D-051)
  - Programs exactly match the 5 approved FTMM programs (D-004)
  - CSV headers match IMPORT_FILE_FORMAT_SPEC.md exactly — files can be uploaded via the normal import pipeline
  - Usage: `python scripts/maintenance/generate_synthetic_data.py --output-dir data/synthetic --seed 42`
  - Files already present at `data/synthetic/` and ready for demo seeding (P7.3 — blocked on cloud accounts)

### Frontend Improvements (Quality of Life)
- **`components/nav.tsx`** — curator "Companies" link renamed to "Employers" — eliminates the label collision with the analytics "Companies" page (`/companies` vs `/curator/companies`).
- **`lib/api-client.ts`** — `apiFetch` now tries to parse the backend's `{ detail: ... }` JSON body on non-2xx responses and uses it as the error message. Previously showed generic "failed (422)" messages; now shows the actual FastAPI validation error.

### P7.8 — Rate Limiting (import endpoint)
- **`app/rate_limiting.py`** — new file: pure-Python sliding-window counter (no `slowapi`/Redis needed)
  - `_within_limit(key)` — 10 calls per 60-second window, thread-safe via `Lock`
  - `import_rate_limit(request: Request) -> None` — FastAPI dependency, raises HTTP 429 when exceeded
  - Keyed by `request.client.host` (IP); resets on process restart (acceptable for MVP single instance)
- **`app/api/imports.py`** — `POST /api/v1/imports` now includes `_rl: None = Depends(import_rate_limit)`
- **`tests/test_rate_limiting.py`** — 6 new tests: sliding window logic + HTTP 429 trigger + `client=None` fallback
- **Test isolation** — `test_imports_endpoint.py`, `test_import_atomicity.py`, `test_quarterly_e2e.py` all override `import_rate_limit` to `lambda: None` so the in-memory counter does not bleed across the 40+ import test calls

### Quality Gates — All Green
- **ruff:** ✅ all checks passed (55 app files + test files)
- **mypy strict:** ✅ success — no issues in 55 source files
- **pytest:** ✅ **647 passed** (rate limiter +6; audit: −4 dead-code tests, +2 country-clause tests)
- **vitest (frontend):** ✅ **23 passed** — 4 test files across lib/
- **ESLint:** ✅ 0 errors, 0 warnings (includes `__tests__/` files)
- **TypeScript:** ✅ 0 errors (includes `__tests__/` files)
- **Next.js build:** ✅ compiled — 15 routes (unchanged)

---

## Current State of the Codebase

### Backend routes active (all require JWT + appropriate permission)

**Curator routes (Phase 3–4):**
- `POST /api/v1/imports` — upload CSV/XLSX (10 MB limit), stage rows
- `GET /api/v1/imports/{id}` / `{id}/rows` — batch status / paginated rows
- `POST /api/v1/commit` — commit batch under snapshot
- `POST /api/v1/alumni/{id}/validate` — curator gate (D-024)
- `GET /api/v1/alumni` / `{id}` — list / get alumni
- `GET /api/v1/dedup/candidates` / `POST .../resolve` — dedup workflow
- `GET/POST /api/v1/snapshots` — snapshot management
- `GET/PATCH /api/v1/companies` / `.../aliases` — company management

**Analytics routes (Phase 5):**
- `GET /api/v1/analytics/filter-options` — dropdown values for filter bar
- `GET /api/v1/analytics/overview` — 4 KPIs + alumni-by-program/year
- `GET /api/v1/analytics/career-outcomes` — Employed vs Not Reported (D-048)
- `GET /api/v1/analytics/companies` — top employers
- `GET /api/v1/analytics/industries` — industry + sector breakdown (D-042)
- `GET /api/v1/analytics/geography` — country + city distribution
- `GET /api/v1/analytics/directory` — paginated, filterable, searchable alumni list
- `GET /api/v1/analytics/alumni/{id}` — alumnus profile + career history (D-047)

### Frontend routes active (15 routes, all dynamic)

**Auth:** `/login`  
**Dashboard:** `/` (Overview), `/careers`, `/companies`, `/industries`, `/geography`, `/directory`, `/directory/[id]`  
**Curator:** `/curator/import`, `/curator/validation`, `/curator/dedup`, `/curator/companies`, `/curator/snapshots`  
**Admin:** `/admin`

### Test files (24 total)
```
tests/test_analytics.py              41 tests  ← audit: −4 dead-code, +2 country-clause
tests/test_aggregation_edge_cases.py 31 tests  ← NEW (P7.6)
tests/test_audit_service.py           6 tests
tests/test_auth_dependencies.py      24 tests
tests/test_commit.py                 40 tests
tests/test_company_api.py            25 tests
tests/test_company_normalization.py  25 tests
tests/test_dedup.py                  52 tests
tests/test_dedup_queue.py            22 tests
tests/test_health.py                  1 test
tests/test_import_atomicity.py        7 tests
tests/test_import_parser.py          34 tests
tests/test_imports_endpoint.py       32 tests
tests/test_industry_classification.py 13 tests
tests/test_location_normalization.py  29 tests
tests/test_me_endpoint.py            17 tests
tests/test_program_matcher.py        35 tests
tests/test_quarterly_e2e.py          29 tests  ← NEW (P7.1)
tests/test_role_seniority.py         91 tests
tests/test_snapshot.py               35 tests
tests/test_user_provisioning.py      18 tests
tests/test_users_endpoint.py         19 tests
tests/test_rate_limiting.py           6 tests  ← NEW (P7.8)
tests/test_validation_status.py      15 tests
                               TOTAL 647 tests
```

---

## Remaining Phase 7 Tasks

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| **P7.3** | Seed demo DB with synthetic data; verify every page + filter | **Blocked** | Blocked on P0.8–P0.11 (Supabase/Railway accounts) |
| **P7.5** | README with screenshots/GIFs, live demo link | Medium | Blocked on P7.3 (needs live deploy) |
| **P7.7** | Frontend tests | ✅ Complete | 23 tests: buildQueryString, apiFetch, FilterProvider, AuthProvider |
| **P7.8** | Rate limiting (import endpoint) | ✅ Complete | 10/min per IP; `import_rate_limit` FastAPI dep; 6 tests |
| **P7.9** | Production deploy: CORS lock-down, env/secrets, migration-on-deploy | **Blocked** | Blocked on P0.8–P0.11 (Supabase/Railway/Vercel accounts) |

**P7.1:** ✅ Complete (E2E tests + curator runbook)  
**P7.2:** ✅ Complete (synthetic data generator + Q1/Q2 CSV files)  
**P7.4:** ✅ Complete (runbook + README)  
**P7.6:** ✅ Complete (test hardening)  
**P7.7:** ✅ Complete (23 frontend tests: vitest + RTL)  
**P7.8:** ✅ Complete (rate limiting, 647 backend tests)

---

## Security Constraints (Carry Forward Verbatim)

- Do NOT touch source files `BUKU TS 2025.pdf`, `Tracer Study FTMM - 2025.pdf`, or PRD .docx
- Provide `.env.example` (keys only, NO values)
- Do NOT attempt P0.8–P0.11 (Supabase/Railway/Vercel/CORS-secrets) — needs user accounts
- Use synthetic data only until legal preconditions R-001/R-002 are cleared
- Build ONLY approved scope — everything traces to DECISIONS.md (D-001–D-051)
- No AI/LLM/chatbot/RAG/recommender/confidence-scoring/predictive features
- All matching/validation/dedup is deterministic and curator-controlled
- Only `validated` alumni appear in analytics (D-047) — enforced in `build_alumni_where()`
- Employment reported as "Employed vs Not Reported" (D-048) — never assert unemployment rate
- Frontend never touches the database — all data access through FastAPI

---

## Technical Notes

### Venv for backend tests
```
cd backend/fastapi-app
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

### ESLint suppression — `react-hooks/set-state-in-effect`
React Compiler ESLint v7 fires on synchronous `setState` at the TOP of `useEffect` body only.
Async `.then()` callbacks do NOT need suppression. Pattern:
```tsx
useEffect(() => {
  // eslint-disable-next-line react-hooks/set-state-in-effect
  setLoading(true);   // synchronous — suppress here only
  fetch().then(data => setState(data));  // async — no suppression needed
}, [deps]);
```

### mypy — `sa.ColumnElement[bool]`
`sa.ColumnElement` in SQLAlchemy 2.0 is generic. Use `sa.ColumnElement[bool]` for WHERE clauses.

### Import size guard
`POST /api/v1/imports` now reads at most `10 MB + 1 byte` and returns HTTP 413 if exceeded.
`csv.Error` (malformed CSV fields) is now caught and returned as HTTP 400.

### Rate limiting
`POST /api/v1/imports` enforces 10 uploads/minute per IP via `app/rate_limiting.py`.
Implemented as a pure-Python sliding-window counter (no `slowapi`/Redis) — in-memory, resets on restart.
Tests that POST to `/api/v1/imports` must add `app.dependency_overrides[import_rate_limit] = lambda: None`
to prevent the shared counter from bleeding across tests. Done in:
`test_imports_endpoint.py`, `test_import_atomicity.py`, `test_quarterly_e2e.py`.

### Source types for import API
`source_type` must be one of: `"Tracer Study"`, `"LinkedIn"`, `"Verified Faculty Record"` (case-sensitive, these match `CAPTURE_SOURCE.source_type` seed values).

### D-024 curator gate
`validation_status=validated` is ONLY set via `POST /api/v1/alumni/{id}/validate`. The commit pipeline never sets `validated`.

### D-031 caller-owned transaction
All services add rows to the SQLAlchemy session but never `session.commit()`. The FastAPI route owns the commit.

### OverviewResult fields
`OverviewResult` uses `total_alumni` (not `total_validated`). `total_validated` is on `CareerOutcomesResult` only.

### Nav label disambiguation
The analytics "Companies" page (`/companies`) is now distinct from the curator "Employers" link (`/curator/companies`) in the nav — renamed to avoid confusion.

---

## How to Resume

1. Verify quality gates:
   ```
   cd backend/fastapi-app && .\.venv\Scripts\python.exe -m pytest tests/ -q
   cd frontend/nextjs-app && pnpm lint && pnpm typecheck && pnpm build
   ```

2. **All unblocked Phase 7 tasks are complete.**  
   The only remaining tasks (P7.3, P7.5, P7.9) all require cloud accounts.  
   See next section for what you need to provide.

4. **For live demo: P0.8–P0.11 (user must provide Supabase/Railway/Vercel credentials)**
   - Then P7.3: seed with `data/synthetic/synthetic_alumni_2025_Q*.csv`
   - See `docs/CURATOR_RUNBOOK.md` for the exact import workflow
   - Then P7.5: add screenshots to README
