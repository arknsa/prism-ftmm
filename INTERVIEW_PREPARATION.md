# Interview Preparation

**Project:** FTMM Alumni Intelligence Dashboard  
**Format:** 30 model Q&A pairs across 7 dimensions. Every answer is grounded in the actual implementation — refer to specific files, decisions, and test counts.

---

## Architecture Questions

### Q1. Walk me through the overall architecture of this project.

The system is three layers in a strict topology: a Next.js frontend on Vercel, a FastAPI
backend on Railway, and PostgreSQL on Supabase. The single most important constraint is that
the frontend never reads from or writes to the database directly — all data access goes
through FastAPI. This is Decision D-031.

The reason matters: when all data access flows through one gateway, you get one place to
enforce business rules, one place to wire audit logging, and one place to enforce RBAC.
If the frontend could query the database directly, you'd have business rules scattered
across two systems and audit logging would be impossible.

Authentication is split from authorization — Supabase Auth handles login and issues a JWT
carrying only the user UUID. FastAPI verifies the JWT signature, then looks up the user's
role and permissions from our application database. Roles are never in the JWT. That's
D-043, and it means permissions can be revoked instantly without waiting for tokens to expire.

### Q2. Why did you choose this three-tier topology over alternatives like Next.js Route Handlers that query Supabase directly?

The temptation is to use Next.js Server Actions or Route Handlers with the Supabase client
directly — it's faster to set up. But it fragments business logic. The validation gate
(only `validated` alumni enter analytics), audit logging (every mutation recorded with
actor + timestamp), and RBAC enforcement would all need to be duplicated or carefully
coordinated between the Next.js server and the Supabase client.

With a single FastAPI gateway, I can write `build_alumni_where()` once, and every analytics
query — regardless of which endpoint calls it — applies the validation gate. There's no
way to accidentally bypass it. The tradeoff is an extra network hop, which is acceptable
at this scale (100–1,000 alumni).

### Q3. How does the snapshot model work, and what are its limitations?

Every `CAREER_RECORD` has a `snapshot_id` foreign key pointing to a `REFRESH_SNAPSHOT` row
with a quarter label like `2025-Q1`. When a curator commits an import, all the career records
in that batch are tagged with the current snapshot.

The analytics endpoints accept a `snapshot_id` filter. When set, the query restricts to career
records from that snapshot. This gives point-in-time reporting — a faculty member can look at
`2025-Q1` data six months later and get the same numbers.

The limitation is that master entities — companies, industries, alumni profiles — are not
versioned. If a company's industry classification changes, it propagates retroactively across
all snapshots. This is an accepted MVP trade-off documented in DECISIONS.md. The point-in-time
guarantee is at the career-record grain, not the master-entity grain.

### Q4. How does the global filter bar work across all six analytics pages?

There's a `FilterContext` (in `lib/filter-context.tsx`) that wraps the entire dashboard layout.
It stores the current filter state — study program, graduation year, industry, company, country,
snapshot quarter — and exposes `setFilter`, `clearFilters`, and `toQueryParams`.

Every analytics page calls its data-fetching hook with `toQueryParams()` appended to the URL.
When a filter changes, all pages re-fetch because they all read from the same context.

On the backend, the `_parse_filters()` dependency in `app/api/analytics.py` reads the query
parameters and constructs an `AnalyticsFilters` dataclass. This gets passed to the service
layer, where three functions build WHERE clauses: `build_alumni_where()` for alumni-level
filters, `build_career_where()` for career-level filters, and `build_country_clause()` for
the country dimension, which requires a special `IN` subquery because country lives on `COMPANY`
via `LOCATION`, not on `CAREER_RECORD`.

---

## Backend Questions

### Q5. Explain the import pipeline from file upload to committed data.

The pipeline has six stages:

1. **Upload** — the curator POSTs a CSV or XLSX to `/api/v1/imports`. The endpoint reads up
   to 10 MB + 1 byte and returns HTTP 413 if exceeded. File extension and `source_type` are
   validated. The `import_rate_limit` dependency enforces 10 uploads/minute/IP.

2. **Parse** — `parse_import()` in `import_parser.py` reads the file, maps columns to a
   canonical shape, and creates `StagingRow` objects. The entire operation is wrapped in
   a transaction with an `IMPORT_BATCH` record. If parsing fails, the transaction rolls back
   — no orphan batch, no orphan audit entry.

3. **Normalization** — when the curator commits a batch, each staged row passes through:
   program matching (20+ variant aliases → 5 canonical programs), company normalization
   (alias lookup → canonical company, create on first sight), industry classification,
   location normalization, and role/seniority classification.

4. **Deduplication** — Tier 1: if `linkedin_url` matches an existing alumnus, auto-link.
   Tier 2: if normalized name + program + year matches, create a `DedupCandidate` for
   curator review.

5. **Commit** — `commit_batch()` writes `ALUMNI` rows and `CAREER_RECORD` rows tagged with
   `snapshot_id`. It enforces the one-current-record invariant by setting `is_current = false`
   on the previous record before inserting the new one.

6. **Audit** — every mutation writes to `AUDIT_LOG` with old/new values, actor, and timestamp.

### Q6. How does the RBAC system work? Walk me through a request lifecycle.

A curator POSTs to `/api/v1/imports`. The route signature includes:
```python
user: AuthenticatedUser = Depends(require_permission("import:run"))
```

`require_permission("import:run")` is a factory that returns a dependency function. That
function calls `get_current_user()`, which calls `verify_jwt()`.

`verify_jwt()` reads the `Authorization: Bearer <token>` header, decodes the JWT with
`SUPABASE_JWT_SECRET` using HS256, validates `sub` and `exp`, and returns `TokenClaims`.

`get_current_user()` takes those claims, queries `APP_USER` by `supabase_uuid = claims.sub`,
joins to `ROLE`, queries `ROLE_PERMISSION → PERMISSION` to get the permission name list,
and returns an `AuthenticatedUser` with a frozenset of permissions.

Back in `require_permission`, it checks: `"import:run" in user.permissions`. If not,
HTTP 403. If yes, the route handler receives the `AuthenticatedUser` and proceeds.

Roles never come from the JWT. Permissions are loaded from the DB on every request.

### Q7. How did you handle the country filter bug you found during the engineering audit?

The analytics endpoints accepted a `country` query parameter and the frontend sent it correctly,
but four of the six endpoints (Overview, Career Outcomes, Companies, Industries) silently ignored it.
Only Geography and Directory applied it.

The root cause: `build_career_where()` builds WHERE clauses for `CAREER_RECORD`, but country
lives on `LOCATION`, which is linked via `COMPANY`. Applying the country filter requires a
`Company → Location` join that `build_career_where()` doesn't perform.

The fix was `build_country_clause()` in `analytics_filters.py`. It returns a self-contained
SQLAlchemy `IN` subquery:
```sql
career_record.company_id IN (
    SELECT company_id FROM company
    JOIN location ON company.location_id = location.location_id
    WHERE location.country = :country
)
```
This composes with any query that references `CAREER_RECORD` without requiring a new join
at each call site. I applied it in all four affected functions and added two regression tests
that compile the clause to SQL and assert the structure.

### Q8. Why expose the rate limiter as a FastAPI dependency instead of middleware?

Middleware applies to all routes unconditionally. I only want rate limiting on
`POST /api/v1/imports`. Putting it in middleware would require route-path matching logic
inside middleware — messy and fragile.

More importantly, tests need to override it. The 40+ test calls to the import endpoint all
come from `127.0.0.1` in TestClient. After 10 calls, subsequent tests would get HTTP 429.

By exposing `import_rate_limit` as a FastAPI dependency, test fixtures can do:
```python
app.dependency_overrides[import_rate_limit] = lambda: None
```
This cleanly disables rate limiting for those tests without touching the actual implementation.
This pattern — exposing infrastructure as overrideable dependencies — is a core FastAPI idiom.

### Q9. Why does the service layer never call `session.commit()`?

D-031: the route layer owns the transaction. Services are called from routes; routes commit.
This means:
- A route can call multiple services in sequence and commit once at the end.
- If any service raises an exception, the route's exception handler calls `session.rollback()`.
- No partial writes — the entire operation succeeds or the entire operation rolls back.
- Services are easier to test: they just need a session fixture, no commit/rollback mechanics.

This is explicitly tested in `test_import_atomicity.py` — if parsing fails mid-batch, the
test verifies that no `IMPORT_BATCH` or `STAGING_ROW` rows were committed.

---

## Frontend Questions

### Q10. How does authentication work on the frontend?

`AuthProvider` in `lib/auth-context.tsx` wraps the application. On mount, it calls `getMe()`
— the `/me` endpoint on FastAPI — with the Supabase session token attached.

If the backend returns HTTP 401, `AuthProvider` calls `supabase.auth.signOut()` and uses
`router.replace("/login")` to redirect. This handles the case where the Supabase session
is valid but the FastAPI backend can't verify it (e.g. wrong JWT secret in env).

If the backend returns HTTP 200, the user object is stored in context and all child components
can read it via `useAuth()`.

The Supabase client in `lib/supabase/client.ts` handles session persistence and token refresh.
The `apiFetch()` wrapper in `api-client.ts` attaches the current Supabase session token as
`Authorization: Bearer <token>` on every request.

### Q11. What was the hardest part of the frontend test setup?

Three things:

**`vi.hoisted()` for mock refs.** Vitest 4 hoists `vi.mock()` factory functions above all
imports. This means a `const mockGetMe = vi.fn()` defined before the mock factory is
actually evaluated after the factory runs. Any mock ref used inside a factory must be created
with `vi.hoisted(() => vi.fn())`, which runs before the hoisting.

**Module-scope `console.error` suppression.** `auth-context.tsx` calls `console.error()` on
non-401 failures. happy-dom v20 intercepts console calls via an async RPC to the vitest
reporter. When the test environment tears down, that RPC is still in-flight and causes
`EnvironmentTeardownError`. The fix is `vi.spyOn(console, "error").mockImplementation(() => {})`
at module scope — outside any `describe` or `beforeEach`, so it's never restored during teardown.

**`globals: false` in vitest config.** All vitest APIs (`describe`, `it`, `expect`, `vi`,
`afterEach`) must be explicitly imported. The error message says `afterEach is not defined`,
which sends you hunting for the wrong thing at first.

### Q12. How does the filter context drive data re-fetching across pages?

`FilterContext` is a React context holding six filter values. Every analytics page's
data-fetching hook uses `toQueryParams()` as a dependency — when any filter changes, the
hook re-fetches with the new query string.

The filter bar component reads from and writes to `FilterContext` directly. Because it's
mounted in the dashboard layout (not inside any individual page), it persists across navigation.
Switching from Overview to Career Outcomes preserves the current filter state.

`toQueryParams()` uses `buildQueryString()` — a pure utility tested in
`build-query-string.test.ts` — which filters out null/undefined values so the URL stays
clean when filters are unset.

---

## Database Questions

### Q13. How does the partial unique index for `is_current` work?

PostgreSQL supports partial indexes — indexes with a `WHERE` clause. The migration creates:
```sql
CREATE UNIQUE INDEX uq_career_record_current
ON career_record (alumni_id)
WHERE is_current = true;
```
This enforces: for any given `alumni_id`, there can be at most one row where `is_current = true`.
Rows where `is_current = false` are excluded from the index entirely.

The commit service sets `is_current = false` on the previous current record before inserting
the new one, so the constraint is never violated. But if application code had a bug and tried
to insert two current records for the same alumnus, the DB would raise a unique-violation
error — a database-level safety net.

### Q14. Why use JSONB for `AUDIT_LOG.old_values` and `new_values`?

The audit log needs to capture arbitrary mutations across 16 different tables. A typed
schema for audit log entries would require knowing in advance every field of every table —
and maintaining it whenever the schema changes.

JSONB gives us:
- Schema flexibility: any dict can be stored.
- Queryability: PostgreSQL can index and query into JSONB fields with `->` operators.
- Human readability: values are stored as JSON, not binary blobs.

The tradeoff is that JSONB isn't strongly typed at the DB level. But since audit entries
are written by application code (via `write_audit_entry()`), and the values are typed
dicts in Python, this is acceptable.

### Q15. How does Alembic know the DB URL without it being in `alembic.ini`?

`migrations/env.py` imports `app.config.get_settings()` and calls `settings.database_url`.
`get_settings()` reads from environment variables (or `.env` file via pydantic-settings).

`alembic.ini` has a placeholder `sqlalchemy.url = ` but the env.py overrides it
programmatically before the migration runs. This means:
- No secret is ever in a committed file.
- The same migration file works locally (reads `.env`) and in CI/Railway (reads env vars).
- The `alembic upgrade head` in `railway.toml` picks up `DATABASE_URL` from Railway's env.

### Q16. Why use the Supabase **pooler** URI instead of the direct connection string?

Supabase Postgres runs behind PgBouncer (their connection pooler). The direct connection
string bypasses PgBouncer and connects directly to Postgres. At low concurrency this is fine,
but Railway's single-instance FastAPI + SQLAlchemy will open a connection pool. With the
direct URI, each SQLAlchemy connection holds a Postgres connection open, exhausting the
connection limit quickly.

The transaction pooler URI goes through PgBouncer in transaction mode: a Postgres connection
is borrowed for the duration of a single transaction and returned to the pool afterward.
SQLAlchemy's `pool_pre_ping=True` guards against stale connections after PgBouncer resets.

---

## Security Questions

### Q17. Walk me through how the system prevents a non-curator from importing data.

`POST /api/v1/imports` has `user: AuthenticatedUser = Depends(require_permission("import:run"))`.

`require_permission("import:run")` calls `get_current_user()` which calls `verify_jwt()`.
`verify_jwt()` decodes the JWT — if it's missing, malformed, or expired, HTTP 401.
`get_current_user()` looks up the `APP_USER` by Supabase UUID — if not found or inactive, HTTP 403.
It loads the user's permissions from `ROLE_PERMISSION`.
`require_permission` checks `"import:run" in user.permissions` — if not present, HTTP 403.

A Faculty Viewer role does not have `import:run` in their permission set (see ROLE_PERMISSION_MATRIX.md).
They will get HTTP 403. The route handler never executes.

### Q18. How do you ensure that unvalidated alumni never appear in analytics?

`build_alumni_where()` in `app/services/analytics_filters.py` always starts with:
```python
clauses = [Alumni.validation_status == ValidationStatus.validated]
```
This list is then extended with any other filter dimensions. Every analytics query passes
its alumni joins through this function. There is no parameter, no flag, no environment
setting that bypasses it.

The alternative — checking `validation_status` in each endpoint separately — would mean
one missed check exposes all data. A structural constraint in a shared function means
it's impossible to forget.

This is tested in `test_aggregation_edge_cases.py` — `TestD047FilterGuard` verifies that
`build_alumni_where()` always includes the validation guard.

### Q19. What prevents a secret from accidentally being committed to git?

Three layers:

1. **Root `.gitignore`** — patterns `.env`, `.env.*` (except `.env.example`), `*.local`.
   This catches `.env`, `.env.local`, `.env.production`, etc.

2. **`.env.example` convention** — the committed file has keys only, no values.
   `APP_ENV=` not `APP_ENV=production`.

3. **Pre-commit hooks** (`.pre-commit-config.yaml`) — ruff and black run on commit.
   While these don't specifically scan for secrets, the culture of reviewing what's staged
   before committing is established.

A fourth layer for production: Railway and Vercel inject secrets as environment variables
— they never touch the filesystem where git could pick them up.

### Q20. Why is the OpenAPI documentation disabled in production?

`app/main.py` sets `docs_url=None` and `openapi_url=None` when `settings.is_production`.

In development (`APP_ENV=local`), `/docs` is available for developer ergonomics. In production,
exposing the interactive Swagger UI leaks the full API surface area — all endpoint paths,
parameter names, response schemas, and error codes — to anyone who discovers the Railway URL.
All endpoints require a valid JWT, so data isn't exposed directly, but the schema is unnecessary
attack surface. Disabling it costs nothing and removes it.

---

## Testing Questions

### Q21. You have 647 backend tests. How did you decide what to test?

The test distribution reflects risk. The highest-risk layers get the most tests:

- `test_role_seniority.py` — 91 tests. The seniority classifier is a pure function with
  many edge cases (title variants, abbreviations, case sensitivity). Bugs here silently
  misclassify every affected alumnus's career level.

- `test_dedup.py` — 52 tests. A dedup bug could merge two different people or fail to
  merge the same person, corrupting alumni identity. The identity model is hard to recover from.

- `test_commit.py` — 40 tests. The commit service is the most consequential write operation.
  Bugs here corrupt the main data tables.

Lower-risk layers have fewer tests: `test_health.py` has 1 test because the health endpoint
is a one-liner with no logic.

The general principle: test at the boundary where the most business logic concentrates.
Routes are thin (validate input → call service → return result) and don't need exhaustive
tests. Services contain the logic that must be correct.

### Q22. How do you test the FastAPI endpoints without a real database?

`conftest.py` creates an in-memory SQLite engine at test session startup and runs all
Alembic migrations against it. Each test gets a session that wraps its operations in a
transaction, and `conftest.py` rolls back after each test — so tests don't accumulate state.

The test FastAPI app is created with `TestClient`, and dependency overrides replace the
production `get_session` with the test session. Rate limiting is overridden with `lambda: None`.

SQLite doesn't support all PostgreSQL features (no `JSONB`, no `ENUM` type natively),
but the test suite works around this — enums are mapped to strings in test mode, and JSONB
fields use `JSON` type in SQLite.

### Q23. What's the most valuable test in the test suite and why?

`test_quarterly_e2e.py` — specifically `TestTwoQuarterOrchestration`. It runs the full
two-quarter pipeline: create snapshots, import Q1 data, commit Q1, validate a cohort,
create Q2, import carry-forward + new graduates, commit Q2, then verify that:
- Q1 filter shows only Q1 alumni count.
- Q2 filter shows Q1 + new Q2 graduates.
- The `not_reported_count` arithmetic is correct (D-048).
- The `total_alumni` field never includes unvalidated alumni (D-047).

This test exercises every layer in sequence via the TestClient — it's the closest thing
to a production smoke test without a live database.

---

## Trade-Off Questions

### Q24. Why did you choose FastAPI over Django REST Framework?

The decision wasn't explicitly in DECISIONS.md but the reasoning is straightforward:

FastAPI's dependency injection system is designed for exactly this pattern — RBAC guards
as dependencies, database sessions as dependencies, rate limiters as dependencies. The
`Depends()` model makes these composable and overrideable in tests.

Pydantic v2 is deeply integrated: request bodies, response models, and settings all use
Pydantic, giving consistent validation and free OpenAPI schema generation. mypy strict
mode works well with Pydantic v2's typed models.

Django REST Framework would have worked, but the serializer model is more verbose for a
read-heavy analytics API, and the ORM is less expressive than SQLAlchemy 2.0 for complex
filter-building.

### Q25. Why SQLAlchemy instead of an ORM-less approach (raw SQL or psycopg directly)?

The analytics filter builder (`build_alumni_where()`, `build_career_where()`,
`build_country_clause()`) constructs WHERE clauses programmatically — adding clauses based
on which filters are active. SQLAlchemy's expression language makes this composable and
safe (parameterized queries by default, no SQL injection risk).

With raw SQL strings, composing dynamic WHERE clauses safely requires careful string
formatting or a query builder library — which is essentially reimplementing SQLAlchemy.

SQLAlchemy 2.0 with `Session.execute(select(...))` is typed and readable. The tradeoff is
the ORM overhead for simple queries, but at 100–1,000 alumni scale this is irrelevant.

### Q26. Why not cache analytics queries?

D-039 (architecture principles): correctness and clarity over premature optimization.
At 100–1,000 alumni, a live SQL aggregation takes <50ms. Caching introduces cache
invalidation complexity — when does the cache expire? When a curator validates new alumni?
When a snapshot is committed?

The accepted answer: at MVP scale, live SQL is fast enough, correct by definition, and
simple to reason about. Caching is explicitly called out as a V2 feature when scale requires it.

### Q27. Why an in-memory rate limiter instead of Redis?

Redis would require a separate managed service, adding infrastructure complexity and cost.
The MVP runs on a single Railway instance with a small curator team (a handful of people
uploading files). An in-memory sliding-window counter is sufficient.

The explicit trade-off (documented in `rate_limiting.py`): the counter resets on process
restart. This is acceptable because: (a) Railway restarts are infrequent, (b) the window
is only 60 seconds, and (c) the import endpoint is not a public endpoint — only authenticated
curators can reach it, so abuse is not the primary threat model.

Redis becomes necessary if the backend scales to multiple instances (the counter would need
to be shared) or if the restart-reset gap becomes an exploit.

### Q28. Why not use Next.js Server Actions or Route Handlers for the backend?

Server Actions and Route Handlers could handle simple CRUD, but they fragment the data layer.
The audit log, RBAC enforcement, and the validated-only analytics invariant all need to be
applied consistently. With Server Actions, you'd need to manually ensure every action
audits its mutations, checks permissions, and filters analytics — and there's no single
place to enforce this.

FastAPI as the single gateway gives one place for all of this. The additional network hop
(Next.js → FastAPI instead of Next.js → Supabase directly) is 5–20ms at co-located
Railway/Vercel regions — imperceptible.

---

## 30 Likely Interview Questions — Quick Reference

| # | Question | Core of the answer |
|---|----------|--------------------|
| 1 | Walk me through the architecture | Three-tier; D-031 single gateway; frontend never touches DB |
| 2 | How does auth work? | Supabase Auth = authn (JWT); app DB = authz (roles); D-043 |
| 3 | How do you enforce RBAC? | `require_permission()` factory → Depends(); loads permissions from DB per request |
| 4 | What's the import pipeline? | Upload → parse → stage → normalize → dedup → commit → audit |
| 5 | How is deduplication implemented? | Two-tier deterministic: exact URL → auto-link; candidate key → curator queue |
| 6 | Why "Employed vs Not Reported"? | Absence of data ≠ unemployment; D-048 is structural — the field doesn't exist |
| 7 | How does the filter bar work? | FilterContext → toQueryParams() → all pages re-fetch; AnalyticsFilters on backend |
| 8 | How do you handle transactions? | Services never commit; routes own the transaction; rollback on any exception |
| 9 | What's the hardest bug you found? | Country filter ignored by 4/6 endpoints; fixed with build_country_clause() IN subquery |
| 10 | How many tests do you have and why so many? | 647 backend + 23 frontend; test distribution mirrors business risk |
| 11 | How do you test FastAPI endpoints? | TestClient + in-memory SQLite + dependency overrides for session + rate limiter |
| 12 | How does the snapshot model work? | CAREER_RECORD.snapshot_id → REFRESH_SNAPSHOT; point-in-time at career-record grain |
| 13 | What's the partial unique index for? | Enforces exactly one is_current=true per alumnus at the DB level |
| 14 | Why Supabase? | Managed Postgres + Auth + pooler; all three services from one vendor; fast to provision |
| 15 | Why Railway for the backend? | Docker-free deploy; nixpacks detects uv; env vars; healthcheck; migration-on-deploy |
| 16 | How do migrations run in production? | railway.toml startCommand: alembic upgrade head before uvicorn |
| 17 | How do you prevent secrets in git? | .gitignore covers .env.*; .env.example keys-only; pre-commit hooks |
| 18 | Why disable /docs in production? | Leaks full API surface; disabled via APP_ENV=production; cost = zero |
| 19 | What does the audit log capture? | Table, record ID, action type, old/new values (JSONB), changed_by, changed_at |
| 20 | Why is industry at company level? | An alumnus's industry derives from their employer; changes propagate to all employees |
| 21 | Why no AI for deduplication? | Accreditation requires explainable decisions; probabilistic matches can't be audited |
| 22 | What are the known limitations? | No cache; in-memory rate limiter resets; master entities not snapshot-versioned |
| 23 | How does the CI pipeline work? | GitHub Actions: 7 backend + 7 frontend checks; blocks merge on failure |
| 24 | Why a flat INDUSTRY table? | industry_name + sector_name in one table; one join, two grouping levels; no hierarchy |
| 25 | How does the frontend handle 401? | AuthProvider catches 401 → signOut + router.replace("/login") |
| 26 | Why vitest over Jest? | Faster; ESM-native; compatible with Vite config; globals:false enforces explicit imports |
| 27 | What was the hardest frontend test challenge? | vi.hoisted() for mock refs + module-scope console.error suppression for teardown race |
| 28 | What would you add in V2? | Redis rate limiter, alumni growth trend page, CSP headers, caching/materialized views |
| 29 | How did you enforce code quality? | ruff + black + mypy strict + 670 tests — all CI-gated; pre-commit hooks locally |
| 30 | What's the most important design decision and why? | D-047 (validated-only analytics) — a structural constraint with no bypass path; correctness guaranteed by construction, not by convention |

---

## Behavioral / Portfolio Questions

### Q29. Why did you build this project?

> "I wanted a full-stack project that demonstrates the entire engineering stack — schema
> design, API design, data pipeline, frontend, testing, and deployment — not just a
> simple CRUD app. The alumni analytics domain gave me a real problem: messy data from
> multiple sources, deduplication, normalization, and a data-governance constraint
> (accreditation reporting requires epistemically correct labels). The 'Employed vs Not
> Reported' distinction, for example, wasn't an obvious choice — it required thinking about
> what the data can and cannot say. I wanted to make engineering decisions I could defend,
> document them, and prove they're implemented by pointing to specific tests."

### Q30. What would you do differently?

> "I'd write integration tests for each filter dimension in each analytics endpoint from
> the start. The country filter bug — where four of six endpoints silently ignored the
> country filter — was only caught during a dedicated engineering audit, not during
> feature development. A parametrized test asserting 'for each of these 6 filter dimensions,
> this endpoint applies it correctly' would have caught it immediately.
>
> I'd also add a `Content-Security-Policy` header from day one. I have the other OWASP
> headers in `next.config.ts`, but CSP for an ECharts + Supabase app requires mapping out
> inline script exceptions first. Starting with a strict CSP and relaxing it is easier than
> retrofitting it."
