# Backend API Inventory — PRISM

**Generated from:** live OpenAPI schema (request/response models) + per-route permission guards.
**Totals:** 32 paths · 35 operations · 10 routers.

**Auth model:** All endpoints require a valid Supabase JWT (`Authorization: Bearer <token>`) **except** `GET /health` and `POST /auth/login` (public). Authorization (permission) is enforced from the app DB via `require_permission(...)`; endpoints marked *"any authenticated"* require only a valid JWT + a registered/active `APP_USER`.

**Status legend:**
- **Baseline** — Phases 1–3, frozen production baseline (verified).
- **Implemented (P4)** / **Implemented (P5)** — code present and wired; pending formal phase review/audit.

---

## Identity & Auth

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| GET | `/health` | Liveness + best-effort DB connectivity | Public | — | — | `HealthResponse` | Baseline |
| POST | `/auth/login` | Validate credentials via Supabase, verify active APP_USER, return tokens | Public | — | `LoginRequest` | `LoginResponse` | Baseline |
| POST | `/auth/register` | Provision Supabase user + APP_USER with assigned role | JWT | `user:manage` | `UserCreateRequest` | `UserCreateResponse` | Baseline |
| GET | `/auth/me` | Caller identity, role, permissions (from DB) | JWT | any authenticated | — | `MeResponse` | Baseline |
| GET | `/me` | Same as `/auth/me` (legacy path, kept) | JWT | any authenticated | — | `MeResponse` | Baseline |
| POST | `/users` | Admin provision a new application user | JWT | `user:manage` | `UserCreateRequest` | `UserCreateResponse` | Baseline |
| DELETE | `/users/{user_id}` | Deactivate APP_USER + ban Supabase user | JWT | `user:manage` | — | `UserDeactivateResponse` | Baseline |

## Import pipeline (Phase 3)

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| POST | `/api/v1/imports` | Upload CSV/XLSX, stage all rows, audit (rate-limited 10/min/IP, ≤10 MB) | JWT | `import:run` | multipart (`file`, `source_type`, `source_id`) | `BatchSummary` | Baseline |
| GET | `/api/v1/imports` | List import batches (paginated, filter by `status`/`source_id`) | JWT | `import:run` | query | `PagedImportBatches` | Baseline |
| GET | `/api/v1/imports/{batch_id}` | Batch summary | JWT | `import:run` | — | `BatchSummary` | Baseline |
| GET | `/api/v1/imports/{batch_id}/rows` | Paginated staged rows (filter by `status`) | JWT | `import:run` | query | `PagedStagingRows` | Baseline |

## Dedup review (Phase 4)

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| GET | `/api/v1/dedup/candidates` | List pending dedup candidates | JWT | `dedup:review` | — | `DedupCandidateListOut` | Implemented (P4) |
| GET | `/api/v1/dedup/candidates/{candidate_id}` | Single dedup candidate | JWT | `dedup:review` | — | `DedupCandidateOut` | Implemented (P4) |
| POST | `/api/v1/dedup/candidates/{candidate_id}/resolve` | Curator merge / keep-separate | JWT | `dedup:review` | `DedupResolveIn` | `DedupCandidateOut` | Implemented (P4) |

## Snapshots (Phase 4)

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| POST | `/api/v1/snapshots` | Create a quarterly refresh snapshot | JWT | `snapshot:manage` | `SnapshotCreateIn` | `SnapshotOut` | Implemented (P4) |
| GET | `/api/v1/snapshots` | List snapshots | JWT | `snapshot:manage` | — | `SnapshotListOut` | Implemented (P4) |
| GET | `/api/v1/snapshots/{snapshot_id}` | Single snapshot | JWT | `snapshot:manage` | — | `SnapshotOut` | Implemented (P4) |

## Commit & Alumni curation (Phase 4)

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| POST | `/api/v1/commit` | Commit a staged batch (normalize → alumni/career under snapshot) | JWT | `import:run` | `CommitBatchIn` | `CommitBatchResultOut` | Implemented (P4) |
| GET | `/api/v1/alumni` | List/browse alumni | JWT | `alumni:read` | query | object | Implemented (P4) |
| GET | `/api/v1/alumni/{alumni_id}` | Single alumnus | JWT | `alumni:read` | — | object | Implemented (P4) |
| POST | `/api/v1/alumni/{alumni_id}/validate` | Curator set validation_status | JWT | `alumni:validate` | `ValidateAlumniIn` | object | Implemented (P4) |

## Company & alias normalization (Phase 4)

| Method | URL | Purpose | Auth | Permission | Request | Response | Status |
|--------|-----|---------|------|-----------|---------|----------|--------|
| GET | `/api/v1/companies` | List canonical companies | JWT | `company:read` | — | `CompanyListOut` | Implemented (P4) |
| GET | `/api/v1/companies/{company_id}` | Single company | JWT | `company:read` | — | `CompanyOut` | Implemented (P4) |
| PATCH | `/api/v1/companies/{company_id}` | Update company (industry/location) | JWT | `company:write` | `CompanyUpdateIn` | `CompanyOut` | Implemented (P4) |
| GET | `/api/v1/companies/{company_id}/aliases` | Aliases for a company | JWT | `company:read` | — | `CompanyAliasListOut` | Implemented (P4) |
| GET | `/api/v1/aliases/{alias_id}` | Single alias | JWT | `company:read` | — | `CompanyAliasOut` | Implemented (P4) |
| PATCH | `/api/v1/aliases/{alias_id}/remap` | Remap alias to a different canonical company | JWT | `company:write` | `CompanyAliasRemapIn` | `CompanyAliasOut` | Implemented (P4) |

## Analytics (Phase 5)

All analytics endpoints: **JWT + `analytics:read`**, request via query params.

| Method | URL | Purpose | Response | Status |
|--------|-----|---------|----------|--------|
| GET | `/api/v1/analytics/overview` | Headline KPIs | `OverviewOut` | Implemented (P5) |
| GET | `/api/v1/analytics/filter-options` | Available filter values | `FilterOptionsOut` | Implemented (P5) |
| GET | `/api/v1/analytics/career-outcomes` | Career outcome aggregates | `CareerOutcomesOut` | Implemented (P5) |
| GET | `/api/v1/analytics/companies` | Top employers / company analytics | `CompanyAnalyticsOut` | Implemented (P5) |
| GET | `/api/v1/analytics/industries` | Industry distribution | `IndustryAnalyticsOut` | Implemented (P5) |
| GET | `/api/v1/analytics/geography` | Geographic distribution | `GeographicAnalyticsOut` | Implemented (P5) |
| GET | `/api/v1/analytics/directory` | Paginated alumni directory | `AlumniDirectoryOut` | Implemented (P5) |
| GET | `/api/v1/analytics/alumni/{alumni_id}` | Single alumnus analytics detail | `AlumnusDetailOut` | Implemented (P5) |

---

## Cross-cutting API conventions

- **Status codes:** 200 (read/ok), 201 (create), 400 (bad input / parse), 401 (bad/missing JWT), 403 (permission denied / inactive / unregistered), 404 (not found), 409 (conflict, e.g. duplicate email), 413 (upload too large), 422 (schema validation), 429 (rate limit), 502 (Supabase upstream), 503 (Supabase/auth unconfigured).
- **Pagination:** `page` (≥1), `page_size` (1–200), envelope `{total, page, page_size, items}`.
- **Response models:** every endpoint declares an explicit Pydantic `response_model` (no ORM leakage).
- **OpenAPI:** served at `/openapi.json` + `/docs` + `/redoc` in non-production; disabled when `APP_ENV=production`.
- **Auth in OpenAPI:** auth is enforced via a custom header dependency, not a registered OpenAPI `securityScheme`, so the generated schema does not annotate `security` per route (a documentation-only gap; enforcement is real).

## Known API-level notes (from production audit)

- **M7:** Phase-2 routes (`/auth`, `/me`, `/users`) are unversioned while Phase 3+ use `/api/v1`.
- **M8:** `/auth/register` ≈ `POST /users` and `/auth/me` ≈ `/me` (intentional, kept for compatibility).
- **H1/M2:** `/auth/login` is not rate-limited and uses the service-role key (hardening recommended before real users).
