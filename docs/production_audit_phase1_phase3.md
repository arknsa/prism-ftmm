# Production Audit — Phases 1–3 (PRISM Backend)

**Scope:** FastAPI backend — schema/migrations (Phase 1), authentication/authorization (Phase 2), import pipeline (Phase 3), and shared infrastructure (db, config, main, logging, rate limiting, audit, health).
**Reviewer stance:** Principal Backend Engineer reviewing a production PR.
**Date:** 2026-07-03
**Method:** Static review of every in-scope module + tests. No code was modified. Findings are evidence-based with file references; severities are calibrated, not inflated.

> Note: Phase 4/5 code (dedup, snapshots, commit, company, analytics) exists in the tree but is **out of scope** for this audit and was reviewed only where it intersects Phases 1–3 (e.g. the shared audit service, `get_current_user`).

---

## Severity summary

| ID | Severity | Area | Finding |
|----|----------|------|---------|
| — | **Critical** | — | **None** (see justification below) |
| H1 | High | Auth / Security | `/auth/login` is unauthenticated-rate-limited **and** proxied via the service-role key → brute-force / credential-stuffing exposure |
| H2 | High | Testing | Entire suite mocks the DB session — **zero** integration tests exercise real schema, constraints, SQL, or migrations |
| M1 | Medium | Database | Metadata/migration drift: no `naming_convention`; migration indexes (incl. partial-unique integrity indexes) not declared in models |
| M2 | Medium | Auth | Login uses service-role key instead of the anon key; `SUPABASE_ANON_KEY` present in `.env` but unbound in config |
| M3 | Medium | Perf / Security | In-memory rate limiter: unbounded key growth, per-process only, keyed on `request.client.host` (proxy IP behind Railway) |
| M4 | Medium | Import / API | `source_id` not validated vs `source_type`/existence; invalid `source_id` → FK error → HTTP 500 (should be 400) |
| M5 | Medium | Security | XLSX decompression-bomb risk — only compressed upload size is capped |
| M6 | Medium | Perf | `get_current_user` runs 2 DB queries on every authenticated request (hot path); no caching |
| M7 | Medium | API Design | Versioning inconsistency — `/auth`, `/me`, `/users` unversioned vs `/api/v1/*` elsewhere |
| M8 | Medium | Code Quality | Duplication — `/auth/register`≈`POST /users`, `/auth/me`≈`/me`, `_get_supabase_client` copy-pasted |
| M9 | Medium | Auth | Brittle Supabase error handling (string-matching); orphaned-Supabase-user on partial failure |
| M10 | Medium | Observability | No request-id/correlation middleware, no metrics, no tracing |
| L1 | Low | Database | FK index gaps on growth tables |
| L2 | Low | Prod Readiness | Health endpoint conflates liveness+readiness; unauthenticated DB ping |
| L3 | Low | Auth | JWT audience not validated; no clock-skew leeway |
| L4 | Low | Perf | Offset pagination degrades at depth |
| L5 | Low | Security | CSV formula-injection latent risk (sanitize on future export, not storage) |
| L6 | Low | Security | PII (emails) in application logs |
| L7 | Low | Database | No connection-pool tuning (`pool_pre_ping` present ✓) |
| L8 | Low | Prod Readiness | No global exception handler / problem+json; no security-headers middleware |
| L9 | Low | Database | `updated_at` bumped only via ORM `onupdate` (acceptable per D-031) |

**No Critical findings.** Justification: the review found no production-breaking defect or trivially-exploitable vulnerability in the Phases 1–3 code as it currently stands. The one previously-critical item — the `dedup_candidate` model with no migration — was already resolved during the Phase-1 migration audit (migration `0010`). The remaining issues are real but either partially mitigated by external controls (Supabase, Railway) or require specific conditions to bite. H1 and H2 are the closest to Critical and should be addressed before onboarding real users / real data.

---

## 1. Architecture

**Verdict: Strong.** Clean, conventional layering.

- **Layering & dependency direction (good):** `api/` (thin controllers) → `services/` (business logic) → `models/` (ORM) → `db/`. Dependencies point inward; no model imports an API module. Controllers stay thin and delegate (e.g. [api/imports.py](../backend/fastapi-app/app/api/imports.py) delegates to `parse_import`).
- **Service boundaries (good):** Services own logic and take an injected `Session`; the caller owns the commit boundary (documented contract in [services/audit.py](../backend/fastapi-app/app/services/audit.py), `provision_user`, `authenticate_user`). This is consistent and testable.
- **Separation of concerns (good):** RBAC is a dependency factory ([dependencies/rbac.py](../backend/fastapi-app/app/dependencies/rbac.py)); auth resolution is a dependency ([dependencies/auth.py](../backend/fastapi-app/app/dependencies/auth.py)); audit is a single-entry service.
- **M7 (Medium) — domain/API inconsistency:** Phase-2 routers are unversioned (`/auth`, `/me`, `/users`) while Phase 3+ are `/api/v1/*`. This fragments the public surface and complicates future versioning. *Recommendation:* mount Phase-2 routers under `/api/v1` too (or document the split deliberately).
- **M8 (Medium) — duplication:** `/auth/register` is functionally identical to `POST /users` (both wrap `provision_user`); `/auth/me` duplicates `/me`; `_get_supabase_client()` is copy-pasted in [api/auth.py](../backend/fastapi-app/app/api/auth.py) and [api/users.py](../backend/fastapi-app/app/api/users.py). *Recommendation:* extract one Supabase-client dependency (`app/dependencies/supabase.py`); decide whether `/auth/*` or `/users`+`/me` is canonical and make the other delegate or retire.

---

## 2. Database

- **SQLAlchemy usage (good):** Modern 2.0 `Mapped[...]`/`mapped_column`, `select()`, typed sessions. No legacy Query API. Bulk insert uses `session.execute(insert(StagingRow), [...])`.
- **Transaction handling (good):** Import is transactional with verified rollback; `get_session` closes in `finally` (uncommitted work rolls back on close). Caller-owns-commit contract is consistent.
- **M1 (Medium) — metadata/migration drift:** `Base` has no `MetaData(naming_convention=...)` ([db.py:19](../backend/fastapi-app/app/db.py#L19)), and the indexes created in migrations `0006`/`0008`/`0009`/`0010` (including the **partial-unique** indexes enforcing D-020 "one current job" and D-044 "unique linkedin_url") are **not declared in the models**. Because [env.py](../backend/fastapi-app/migrations/env.py) uses `target_metadata = Base.metadata` for autogenerate, `alembic revision --autogenerate` would emit `drop_index(...)` for these — silently discarding performance **and data-integrity** indexes if applied unreviewed. *Recommendation:* add a `naming_convention` and declare indexes in `__table_args__` so metadata == migrations; verify with an empty-diff autogenerate.
- **M6 (Medium) — hot-path query count:** `get_current_user` ([dependencies/auth.py:121-147](../backend/fastapi-app/app/dependencies/auth.py#L121-L147)) runs **2 queries per authenticated request** (user+role join, then permissions). Not an N+1, but it's on every request. *Recommendation:* single query via join, and/or short-TTL cache of `role_id → permissions` (roles/permissions are near-static).
- **N+1 (good):** None found in Phases 1–3 endpoints. List/rows endpoints use `count()` + one paged query.
- **Bulk operations (good):** Staging insert is a single executemany (Phase 3).
- **Locking (acceptable):** No explicit locking; `SELECT … FOR UPDATE` not needed at this stage. Note for Phase 4 commit.
- **Connection management (L7, Low):** Lazy global engine with `pool_pre_ping=True` (good — guards stale Supabase pooler connections). No `pool_size`/`max_overflow`/`pool_recycle` tuning; defaults are fine for a small team but should be set explicitly before scaling. App sits behind Supabase's session pooler → some double-pooling (benign).
- **L1 (Low) — FK index gaps:** Several FK columns on growth tables are unindexed: `company_alias.company_id` (CASCADE + reverse lookup), `audit_log.changed_by` (full scan on user delete), `alumni.source_id`, `career_record.source_id`. `0009`/`0010` index their FKs well; the earlier migrations are inconsistent. Low impact at current volume; index before growth. (Fixing this interacts with M1 — declare in models too.)
- **L9 (Low):** `updated_at` uses ORM `onupdate` only ([security.py:88](../backend/fastapi-app/app/models/security.py#L88), [alumni.py:97](../backend/fastapi-app/app/models/alumni.py#L97)); raw-SQL/Supabase-direct writes won't bump it. **Acceptable** — D-031 makes the app the sole write gateway.

---

## 3. API Design

- **Response schemas (good):** Every endpoint declares an explicit `response_model`; no ORM objects leak; no over-exposure (covers OWASP API3). Pydantic v2 throughout.
- **Pagination & filtering (good):** `page`/`page_size` with `ge`/`le` bounds (`page_size ≤ 200`), plus `status`/`source_id` filters on the new list endpoint and `status` on rows.
- **Status codes (mostly good):** 201 for create, 200 for reads, 401/403/404/409/413/422/429 used correctly. **Exception — M4:** an invalid `source_id` surfaces as **500** (see §5).
- **OpenAPI quality (good):** Summaries, docstrings, tags, response models present; interactive docs disabled in production ([main.py:42-43](../backend/fastapi-app/app/main.py#L42-L43)).
- **M7 (Medium):** REST consistency — versioning split (see §1).
- **BOLA note (L, informational):** `GET /api/v1/imports/{batch_id}` lets any `import:run` holder read any batch (batches aren't user-scoped). Acceptable because `import:run` is limited to Admin/Curator (a small trusted set), but worth a conscious note for API1.

---

## 4. Authentication & Authorization

- **D-043 compliance (excellent):** Authorization is loaded **exclusively** from the DB (`APP_USER → ROLE → ROLE_PERMISSION`); the JWT `role` claim is captured for logging only and never used for authz ([dependencies/auth.py:102-105](../backend/fastapi-app/app/dependencies/auth.py#L102-L105)). `require_permission` inspects `AuthenticatedUser.permissions`, never claims. Login additionally verifies the user is a provisioned, active `APP_USER` before returning tokens.
- **JWT validation (good, with L3):** HS256 pinned (prevents alg-confusion), required-claims (`sub`, `exp`) validated, expiry handled. **L3 (Low):** `verify_aud=False` (documented) and no `leeway` for clock skew — both minor defense-in-depth gaps.
- **RBAC correctness (good):** Guard returns 403 on missing permission, propagates 401 from upstream; distinct guard identities per permission (dependency-cache safe). Covered by tests.
- **Privilege-escalation risks (low):** Roles come from DB; a forged/again `role: "admin"` JWT claim grants nothing. *Recommendation (testing):* add an explicit test asserting a JWT `role` claim is ignored (see §9).
- **H1 (High) — login brute-force exposure:** `POST /auth/login` ([api/auth.py](../backend/fastapi-app/app/api/auth.py)) has **no rate limiting** (only `POST /api/v1/imports` does). Worse, it authenticates via a Supabase client built with the **service-role key** ([api/auth.py `_get_supabase_client`], [authentication.py](../backend/fastapi-app/app/services/authentication.py)); service-role requests may **bypass gotrue's built-in auth throttling**, removing the external mitigation a normal anon-key login would enjoy. Net: an unthrottled credential-stuffing surface. *Recommendation:* add a strict per-IP+per-email rate limit to `/auth/login`, and switch to the anon key (M2).
- **M2 (Medium) — wrong key + dead config:** User-facing auth should use the **anon** key; `SUPABASE_ANON_KEY` exists in `.env` but is **not** bound in [config.py](../backend/fastapi-app/app/config.py) (only `supabase_service_role_key`/`supabase_jwt_secret` are). So the anon key is currently unusable and login over-privileges the client. *Recommendation:* bind `SUPABASE_ANON_KEY` in settings; use it for `sign_in_with_password`; reserve the service-role key for admin operations (`create_user`, `ban`).
- **M9 (Medium) — brittle error handling & orphans:** `provision_user` string-matches `"already been registered"`/`"already exists"` to map to 409 ([user_provisioning.py:87](../backend/fastapi-app/app/services/user_provisioning.py#L87)); a Supabase wording change silently turns duplicate-email into 502. Also, if the DB write fails after `create_user` succeeds, the Supabase user is **orphaned** (logged, no automatic compensation — documented MVP limitation). *Recommendation:* catch the typed `gotrue.errors.AuthApiError` and branch on its status/code; track orphan-cleanup as a follow-up.
- **Supabase integration (good overall):** Service-role client rebuilt per request (no cross-request secret caching) — a deliberate, sound choice for the admin flows.

---

## 5. Import Pipeline

- **Rollback safety (excellent):** Atomic `parse → flush → stage(bulk) → audit → commit`; any exception rolls back with no orphan batch/audit. Explicitly tested ([test_import_atomicity.py](../backend/fastapi-app/tests/test_import_atomicity.py)).
- **Validation & error handling (good):** Required-field + graduation-year validation; malformed rows are staged with `row_status="error"` + message (non-lossy). Unsupported extension/source → `ValueError` → 400.
- **Logging (good):** Structured completion log with batch/source/counts/actor.
- **M4 (Medium) — source integrity & wrong status code:** `source_id` is accepted from the client and only enforced by the DB FK. An invalid `source_id` makes `flush()` raise `IntegrityError`, which is **not** in the caught `(ValueError, UnicodeDecodeError, csv.Error)` tuple → falls to `except Exception` → **HTTP 500** ([api/imports.py:110-119](../backend/fastapi-app/app/api/imports.py#L110-L119)). Additionally, `source_type` and `source_id` are **not cross-checked** — a client can pair `source_type="LinkedIn"` with a `source_id` that points at a "Tracer Study" row, corrupting provenance (D-046). *Recommendation:* look up `CAPTURE_SOURCE` by `source_id`, verify `source_type` matches, and return 400/404 on mismatch/absence before staging.
- **M5 (Medium) — XLSX decompression bomb:** The 10 MB guard caps **compressed** size; a crafted `.xlsx` (ZIP) can expand to gigabytes. `openpyxl` `read_only=True` mitigates memory somewhat but not a true bomb. *Recommendation:* cap decompressed size / row count during read, or reject workbooks whose declared dimensions exceed a threshold.
- **Scalability / streaming / memory (M, by design):** The whole file is read into memory, fully parsed into a list, then into value-dicts (~3–4× file size transiently). You explicitly chose to defer true streaming; at the ≤10 MB / <5k-row target with a 10/min limit this is acceptable, but it caps vertical headroom and is a mild DoS multiplier under concurrency. Revisit if source files grow.
- **Duplicate-detection preparation (good):** Staging carries the full A1 candidate shape (name/program/year/employer/…); the Phase-4 dedup consumes it. Nothing needed here.

---

## 6. Code Quality

- **Readability, naming, docs (excellent):** Consistent module docstrings tying code to decisions (D-0xx), clear names, thin controllers. Among the best-documented areas reviewed.
- **M8 (Medium) — duplication:** See §1 (register/me/`_get_supabase_client`).
- **Complexity (low):** `_parse_rows` repeats the `_ParsedRow(...)` construction three times for the two error branches + success — mildly WET but readable. Optional: build the base dict once and override `row_status`/`row_error`.
- **Dead code (low):** `SUPABASE_ANON_KEY` in `.env` is unreferenced (M2). Otherwise none of note.
- **Maintainability (good):** Small, single-purpose modules; DI makes everything mockable.

---

## 7. Security (OWASP API Top 10)

- **API1 Broken Object Level Auth (low):** batch reads not user-scoped but gated to a trusted role (see §3).
- **API2 Broken Authentication (H1/M2):** unthrottled login + service-role proxy — the top security concern.
- **API3 Broken Object Property (good):** explicit response schemas; no mass-assignment (request bodies are typed Pydantic models with only intended fields).
- **API4 Unrestricted Resource Consumption:** size guard + rate limit + `page_size` cap (good); **but** XLSX bomb (M5) and rate-limiter memory growth (M3).
- **API5 Broken Function Level Auth (good):** `require_permission` on every privileged route.
- **API8 Security Misconfiguration:** docs off in prod (good); CORS origins come from settings (explicit) with `allow_credentials=True` — safe **provided** origins are never `"*"`; empty default blocks cross-origin (safe). Verify prod origins are explicit.
- **Injection (excellent):** 100% parameterized ORM/Core queries; the only raw SQL is the constant `text("SELECT 1")` in `ping()`. No SQL-injection surface.
- **CSV upload risks (M5 + L5):** decompression bomb (M5, above); **L5** formula/CSV injection — raw cells (e.g. `=CMD|...`) are stored verbatim. Safe at rest and for HTML rendering; becomes a risk only if a future feature **exports** staging/analytics to CSV/XLSX. *Recommendation:* sanitize (prefix `'`) on export, not on ingest.
- **Sensitive logging (L6):** No passwords/tokens are logged (good). Emails and Supabase UUIDs appear in logs/audit (`authentication.py`, `user_provisioning.py`) — PII, acceptable for an internal tool but worth a data-retention note.

---

## 8. Performance

- **Hot path (M6):** `get_current_user` = 2 queries/request; the single biggest optimization opportunity (join + cache).
- **Batching (good):** bulk staging insert (Phase 3).
- **Query optimization (good):** targeted `select()`s; counts via `func.count()`.
- **L4 (Low):** offset pagination `OFFSET n` scans skipped rows; fine now, prefer keyset for large batch histories.
- **Async opportunities (informational):** The stack is fully **sync** (psycopg + sync `Session`, sync route handlers). That's a coherent choice and avoids sync-in-async foot-guns; note that heavy I/O endpoints won't benefit from async concurrency. No action needed unless throughput demands it.
- **Memory (M5/import):** whole-file materialization (see §5).

---

## 9. Testing

- **Strengths:** 683 tests, disciplined mocking, good behavioral coverage of parsing, RBAC, atomicity, and auth flows.
- **H2 (High) — no DB-integration tests:** Every test replaces the session with `create_autospec(Session)`/`MagicMock`. **No test ever executes real SQL** against Postgres (or even SQLite). Consequences: migrations, FK/unique/partial-unique constraints, cascade behavior, `server_default`s, and model↔migration parity are **never verified**. This is precisely why the missing `dedup_candidate` migration was invisible until a manual audit. *Recommendation:* add a thin integration layer — spin up Postgres (testcontainers) or at least SQLite for schema-shape tests — that runs `alembic upgrade head` and exercises a happy-path insert per table plus the two partial-unique constraints.
- **Missing edge cases (Medium):**
  - No test that a JWT `role` claim is ignored for authorization (D-043's core guarantee).
  - No test for `source_id`/`source_type` mismatch or invalid `source_id` (ties to M4).
  - No test for the FK-violation → error-code path.
- **Missing security tests (Medium):** no login brute-force/rate-limit test (endpoint isn't limited — H1), no JWT-tampering/expired-signature integration test at the endpoint boundary, no authz-bypass attempts.
- **Missing performance tests (Low):** none; acceptable for MVP.

---

## 10. Production Readiness

- **Health checks (L2):** `/health` reports liveness + best-effort DB ping ([api/health.py](../backend/fastapi-app/app/api/health.py)). It conflates **liveness** and **readiness**, and performs an **unauthenticated** DB round-trip (minor amplification vector). *Recommendation:* split `/health` (liveness, no DB) from `/ready` (readiness, DB), and consider caching the ping.
- **Observability (M10):** Structured JSON logging is in place from day one (good). Missing: request-id/correlation-id middleware, metrics (Prometheus/OTel), and distributed tracing. For a single-instance MVP this is tolerable; add correlation-id + basic metrics before real traffic.
- **Middleware (L8):** Only CORS. No global exception handler (unhandled errors return FastAPI's default 500 with no structured body / correlation id), no security-headers middleware (some covered by Railway's proxy). Add a global handler emitting `problem+json` with a correlation id.
- **Deployment readiness (good):** `railway.toml` present; secrets sourced from env; docs disabled in prod; JSON logs suited to Railway. **Open ops item (not a code defect):** the live DB has not yet been migrated (`alembic upgrade head` still pending — blocked locally by the port-5432 egress issue documented previously).

---

## Prioritized remediation (proposed — awaiting approval; no code changed)

1. **H1 + M2** — Rate-limit `/auth/login` (per IP **and** per email) and switch it to the anon key (bind `SUPABASE_ANON_KEY` in config). *Highest security value.*
2. **H2** — Add a minimal DB-integration test tier (`alembic upgrade head` + per-table happy path + the two partial-unique constraints). *Closes the class of defect that hid the dedup migration.*
3. **M4** — Validate `source_id` existence and `source_type` match before staging; return 400/404 instead of 500.
4. **M1** — Add `MetaData(naming_convention=…)` + declare indexes in models; prove empty autogenerate diff. *(Do NOT edit frozen migrations 0001–0010 — resolve forward.)*
5. **M3** — Evict idle rate-limit keys, honor `X-Forwarded-For` (trusted proxy), and note the per-process limitation (move to Redis when scaling horizontally).
6. **M5** — Bound XLSX decompressed size / dimensions.
7. **M6** — Collapse `get_current_user` to one query and/or cache role→permissions.
8. **M7, M8, M9, M10** — Versioning consistency; de-duplicate Supabase client + register/me; typed Supabase error handling; correlation-id middleware + basic metrics.
9. **Low items (L1–L9)** — schedule opportunistically; FK indexes (L1) and health split (L2) give the best ratio.

---

## Appendix — What's done well (explicit "no issue" notes)

- **D-043 authorization model** is implemented correctly and defensively; the JWT role claim is provably never trusted.
- **No SQL-injection surface** — fully parameterized ORM/Core; the sole raw statement is a constant.
- **Transactional import with proven rollback** and atomic audit — a common source of bugs, handled well and tested.
- **Explicit, minimal response schemas** — no data over-exposure (API3).
- **Layered architecture with inward dependencies** and thin controllers — easy to reason about and test.
- **Structured JSON logging, size guard, write rate limiting, `page_size` caps, HS256 pinning, docs-off-in-prod** — solid baseline hygiene.
- **Migrations 0001–0010** are clean, downgrade-safe, and PostgreSQL/Supabase-compatible (per the prior migration audit), and are now frozen.

**Bottom line:** Phases 1–3 are a well-architected, well-documented, well-tested-at-the-unit-level foundation. The two items worth blocking on before real users/data are **H1** (login hardening) and **H2** (a real DB-integration test tier); everything else is incremental hardening. No changes were made — awaiting approval to apply any recommendation.
