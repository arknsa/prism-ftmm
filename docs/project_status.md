# Project Status — PRISM Backend

**As of:** 2026-07-03
**Baseline:** Phases 1–3 are **frozen** and verified (see `backend_readiness_report.md`). The live Supabase schema matches migrations `0001`–`0010` exactly; the app boots, serves, and all routers/dependencies resolve.

---

## Completed phases (frozen baseline)

| Phase | Scope | Status | Evidence |
|-------|-------|--------|----------|
| **0** | Bootstrap: app factory, config, JSON logging, `/health` | ✅ Done | `main.py`, `logging.py`, `health.py` |
| **1** | Schema + migrations `0001`–`0010`; deployed to Supabase | ✅ Done · **Frozen** | 17 tables live, `alembic_version=0010`, `backend_database_inventory.md` |
| **2** | Authentication (Supabase) + authorization (D-043 RBAC): `/auth/{login,register,me}`, `/me`, `/users`, guards | ✅ Done · **Frozen** | 683 tests, `backend_architecture.md` §6–7 |
| **3** | Import pipeline: upload → parse (CSV/XLSX) → validate → bulk-stage → audit; list/batch/rows endpoints | ✅ Done · **Frozen** | `import_parser.py`, `imports.py`, atomicity tests |

**Verification artifacts:** `docs/production_audit_phase1_phase3.md`, `docs/backend_readiness_report.md`.

---

## Implemented but pending formal phase gate

The following code **already exists in the repository and is wired into the app**, but has **not** yet gone through the formal phase review/approval used for Phases 1–3. Treat as functional-but-unreviewed until its phase is opened.

| Phase | Scope | Endpoints |
|-------|-------|-----------|
| **4** | Curation & commit: dedup review queue, snapshots, commit pipeline (normalize staged → alumni/career), company/alias curation, alumni validation | `/api/v1/dedup/*`, `/api/v1/snapshots*`, `/api/v1/commit`, `/api/v1/alumni*`, `/api/v1/companies*`, `/api/v1/aliases*` |
| **5** | Analytics & reporting | `/api/v1/analytics/*` (8 endpoints) |

Supporting services already present: `dedup_queue`, `dedup`, `commit`, `snapshot`, `company_normalization`, `location_normalization`, `industry_classification`, `program_matcher`, `role_seniority`, `validation_status`, `analytics`, `analytics_filters`.

---

## Remaining work (roadmap)

1. **Phase 4 formal gate** — audit + approve the curation/commit/dedup/snapshot/company code already in the repo; add DB-integration tests for the commit path (normalization writing real `alumni`/`career_record` rows under a snapshot).
2. **Phase 5 formal gate** — audit + approve analytics; add query-performance checks for aggregation endpoints.
3. **Frontend integration** — Next.js app consumes `/api/v1/*` with Supabase-issued JWTs; finalize CORS origins.
4. **Production hardening** (partly done — e.g. P7.8 upload size guard) — address the audit findings below.
5. **Observability** — correlation-id middleware, metrics, tracing.

---

## Technical debt (from `production_audit_phase1_phase3.md`)

### High
- **H1 — Login hardening:** `/auth/login` is not rate-limited and is proxied with the **service-role** key (may bypass Supabase's own auth throttling) → brute-force exposure. *Fix:* per-IP/per-email rate limit + use the anon key.
- **H2 — No DB-integration tests:** the entire suite mocks the `Session`; real SQL, constraints, and migrations are never exercised (this is why the missing `dedup_candidate` migration was invisible until a manual audit). *Fix:* add a thin integration tier (`alembic upgrade head` + per-table happy path + the two partial-unique constraints).

### Medium
- **M1** — Model/migration drift: no `naming_convention`; migration indexes (incl. partial-unique integrity indexes) not declared in models → autogenerate would drop them. *(Resolve forward; do not edit frozen migrations.)*
- **M2** — `SUPABASE_ANON_KEY` present in `.env` but unbound in config; login over-uses the service-role key.
- **M3** — In-memory rate limiter: unbounded key growth, per-process only, keyed on `request.client.host` (proxy IP behind Railway; ignores `X-Forwarded-For`).
- **M4** — Import: `source_id` not validated vs `source_type`/existence; invalid `source_id` → FK error → HTTP 500 (should be 400); source mismatch corrupts provenance.
- **M5** — XLSX decompression-bomb: only compressed upload size is capped.
- **M6** — `get_current_user` runs 2 DB queries on every authenticated request (hot path); no caching.
- **M7** — API versioning inconsistency (`/auth`, `/me`, `/users` unversioned vs `/api/v1/*`).
- **M8** — Duplication: `/auth/register`≈`/users`, `/auth/me`≈`/me`, copy-pasted `_get_supabase_client`.
- **M9** — Brittle Supabase error handling (string-matching); orphaned-Supabase-user on partial provisioning failure.
- **M10** — Observability gaps: no request-id/correlation, metrics, or tracing.

### Low
- **L1** FK index gaps on growth tables · **L2** `/health` conflates liveness/readiness (unauthenticated DB ping) · **L3** JWT audience not validated, no clock-skew leeway · **L4** offset pagination degrades at depth · **L5** CSV formula-injection latent (sanitize on future export) · **L6** PII (emails) in logs · **L7** no connection-pool tuning (`pool_pre_ping` present ✓) · **L8** no global exception handler / security-headers middleware · **L9** `updated_at` via ORM `onupdate` only.

---

## Known warnings (deployment / readiness)

- **Railway build:** `startCommand` uses `uv run`; confirm Nixpacks provisions `uv` at runtime (ships `uv.lock`) on first deploy.
- **DB connectivity:** the app connects to the Supabase **session pooler (5432)** via libpq multi-IP failover; a raw probe to one pooler IP intermittently times out from some networks. Functional; monitor on deploy.
- **Migrate-on-deploy:** `alembic upgrade head` runs each deploy (idempotent at `0010`).
- **Docs:** `/docs` + `/openapi.json` are disabled when `APP_ENV=production` (by design).

---

## Frozen-baseline policy

Per the current directive, the following are **frozen** and must not change without an explicit unfreeze + a production-breaking justification:

- Alembic migrations `0001`–`0010`
- SQLAlchemy models
- Authentication & authorization (D-043)
- Database schema
- Existing endpoints (Phases 1–3)

Future schema changes start at **`0011_*`**; forward-only. Audit remediations that touch models/config (e.g. M1, M2) are permitted **as new work** but must not alter the frozen migration chain.

---

## Document index

- `docs/backend_architecture.md` — layers, lifecycle, DI, auth/authz, transactions, startup.
- `docs/backend_api_inventory.md` — every endpoint: method, URL, auth, permission, schemas, status.
- `docs/backend_database_inventory.md` — every table: columns, PK/FK, indexes, constraints, relationships, migration.
- `docs/production_audit_phase1_phase3.md` — full production audit (findings + severities).
- `docs/backend_readiness_report.md` — go/no-go verification (10 categories, PASS/WARN/FAIL).
