# Final Engineering Audit

**Date:** 2026-07-02
**Scope:** Repository-wide audit across backend, frontend, and documentation.
**Auditor mode:** Fix genuine engineering issues only. No architecture redesign, no new
features, no cloud-dependent work.

---

## Executive Summary

The repository was audited across all layers (FastAPI backend, SQLAlchemy models, Alembic
migrations, services, APIs, schemas, tests; Next.js frontend, components, contexts, hooks,
API client, tests; and the documentation set). The codebase was already in strong shape —
all quality gates were green before the audit.

The audit found **one genuine correctness bug** (a filter dimension silently ignored by four
of six analytics endpoints), **one piece of dead code**, and **several stale documentation
references**. All were fixed. No architectural inconsistency, no security regression, and no
required-artifact gap was discovered. The three remaining Phase 7 tasks (P7.3, P7.5, P7.9)
remain blocked strictly on cloud infrastructure.

**Result:** The repository is production-ready except for the cloud-dependent deploy/seed
tasks. All backend and frontend validation gates pass.

---

## Issues Found

### ISSUE-1 (Correctness — HIGH): `country` filter silently ignored on 4 of 6 analytics endpoints
- **Where:** `app/services/analytics.py` — `get_overview`, `get_career_outcomes`,
  `get_company_analytics`, `get_industry_analytics`.
- **Symptom:** The global filter bar (`components/filter-bar.tsx`) offers a **Country**
  dropdown, and the frontend correctly forwards `country=` to every analytics endpoint.
  However, only `get_geographic_analytics` and `get_alumni_directory` actually applied the
  country filter. The four aggregation endpoints called `build_career_where(filters)`, which
  never included the country dimension (it requires a `Company → Location` join the helper
  did not perform).
- **Impact:** A user selecting a country would see **inconsistent totals across dashboard
  pages** — Geography correctly scoped to the country, while Overview / Career Outcomes /
  Companies / Industries silently showed all-country data. A data-integrity inconsistency
  visible to any analyst using the country filter.
- **Why it escaped tests:** The existing `TestFilterDimensionPropagation` only asserted that
  the `country` query param reached the `AnalyticsFilters` object (the service was mocked), so
  it never exercised the service's SQL.

### ISSUE-2 (Dead code): `filters_need_company_join()` never used in production
- **Where:** `app/services/analytics_filters.py`.
- **Detail:** The helper was defined and unit-tested but not called by any code path in
  `app/`. After ISSUE-1 was fixed with a self-contained subquery clause, the helper had no
  remaining purpose.

### ISSUE-3 (Documentation — stale): Multiple docs described a "Phase 0" state
- `backend/fastapi-app/app/db.py` — docstrings claimed "Phase 0 has no models" / "Models are
  added from Phase 1 onward" (the schema is complete).
- `frontend/nextjs-app/README.md` — described a "Phase 0 deployable shell" that "shows backend
  health"; claimed ECharts was "installed, unused"; omitted `pnpm test`.
- `backend/fastapi-app/README.md` — "Phase 0 exposes only GET /health. No models yet." and
  "Phase 0 ships one empty baseline migration" (there are 9 migrations and a full API).
- Root `README.md` — stale test counts (`612` and `649`; actual is `647`).
- `NEXT_SESSION_HANDOFF.md` — stale test counts (`649`, `43` analytics tests) after the audit
  changed totals.

---

## Fixes Applied

### FIX-1 — Consistent country filtering (resolves ISSUE-1)
- Added `build_country_clause(filters)` to `app/services/analytics_filters.py`. It returns a
  `CareerRecord.company_id IN (SELECT company_id FROM company JOIN location WHERE country = :c)`
  clause, or `None` when no country filter is active. Being a self-contained subquery, it
  composes with any query that references `CareerRecord` — no explicit Location JOIN required
  at each call site.
- Applied the clause in all four affected functions (`get_overview` career sub-counts,
  `get_career_outcomes`, `get_company_analytics`, `get_industry_analytics`).
- Left `get_geographic_analytics` and `get_alumni_directory` as-is (they already apply the
  country filter correctly via their own Location joins / EXISTS subquery).
- **Scope note:** The alumni-level counts in Overview (`total_alumni`, by-program, by-year)
  intentionally honor only program + graduation_year, matching the pre-existing behavior for
  the other career-scoped dimensions (industry, company). Changing that would invent
  undocumented semantics, so it was deliberately left unchanged.
- **Test:** Added `test_build_country_clause_none_when_no_country` and
  `test_build_country_clause_returns_clause_when_country_set` (the latter compiles the clause
  to SQL and asserts `career_record.company_id IN` + the country literal are present).

### FIX-2 — Removed dead code (resolves ISSUE-2)
- Deleted `filters_need_company_join()` from `analytics_filters.py` and its four tests from
  `test_analytics.py`.

### FIX-3 — Documentation refresh (resolves ISSUE-3)
- `app/db.py` — rewrote the module + `Base` + `get_session` docstrings to describe the current
  state (full ORM schema, migrations under `migrations/versions/`).
- `frontend/nextjs-app/README.md` — rewrote intro, run instructions, and quality gates to
  reflect the 15-route analytics dashboard + Supabase Auth + `pnpm test`.
- `backend/fastapi-app/README.md` — rewrote intro and migrations section (9 migrations, full
  curator + analytics API).
- Root `README.md` — corrected test counts to 647.
- `NEXT_SESSION_HANDOFF.md` — corrected test counts (647 total, 41 analytics, 24 test files)
  and annotated the audit delta.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/fastapi-app/app/services/analytics_filters.py` | +`build_country_clause`, −`filters_need_company_join`, imports Location |
| `backend/fastapi-app/app/services/analytics.py` | country clause applied in 4 aggregation functions |
| `backend/fastapi-app/app/db.py` | docstrings refreshed (no behavior change) |
| `backend/fastapi-app/tests/test_analytics.py` | +2 country-clause tests, −4 dead-code tests |
| `backend/fastapi-app/README.md` | de-staled (API surface + migrations) |
| `frontend/nextjs-app/README.md` | de-staled (dashboard + `pnpm test`) |
| `README.md` | test counts corrected (647) |
| `NEXT_SESSION_HANDOFF.md` | test counts + audit delta |
| `FINAL_ENGINEERING_AUDIT.md` | this report (new) |

No frontend source files required changes — the frontend was already correct (it was the
backend that ignored the filter the frontend sent).

---

## Review-Dimension Findings (12 dimensions)

| # | Dimension | Finding |
|---|-----------|---------|
| 1 | Architecture consistency | ✅ Consistent. Single FastAPI gateway (D-031); services never commit (D-031); analytics validated-only guard centralized (D-047). No redesign needed. |
| 2 | Code duplication | ✅ Low. The country-clause application is a 3-line idiom repeated in 4 functions — acceptable and clearer than over-abstracting; the shared logic lives in `build_country_clause`. |
| 3 | Dead code | ⚠️→✅ Found & removed `filters_need_company_join`. |
| 4 | Naming consistency | ✅ Consistent (`build_*_where`, `get_*`, `*Result` dataclasses, `*Out` schemas). |
| 5 | Type safety | ✅ mypy strict passes (55 files). `build_country_clause` typed `-> sa.ColumnElement[bool] \| None`. Minor: frontend `setFilter` union-widening is a known ergonomic limitation, not a defect. |
| 6 | Error handling | ✅ Import endpoint handles size (413), CSV/parse errors (400), and rolls back atomically. API-client propagates backend `detail`. Auth 401 → redirect. |
| 7 | Security | ✅ RBAC enforced per endpoint; `.env.example` files are keys-only; CORS from settings (no wildcard fallback); rate limiting on import. Only validated alumni in analytics (D-047); employment reported as "Employed vs Not Reported" (D-048). |
| 8 | Performance | ✅ Aggregations use `COUNT(DISTINCT)` in SQL, not Python; directory paginated; country clause is an indexed FK `IN` subquery. |
| 9 | Maintainability | ✅ Clear layer separation; docstrings cite decision IDs. |
| 10 | Test coverage | ✅ 647 backend + 23 frontend. Added regression coverage for the country clause. |
| 11 | Documentation consistency | ⚠️→✅ Stale Phase-0 references and test counts corrected. |
| 12 | Production readiness | ✅ Except cloud-dependent deploy/seed. Health check, lazy engine, `pool_pre_ping`, migration tree 0001–0009 all present. |

### Intentional gaps noted (not defects, not changed)
- **Company filter has no dropdown** in `filter-bar.tsx` (5 of 6 dimensions have UI). Company
  counts can be large; company filtering remains reachable via URL param and the directory.
  Adding a searchable company selector would be a **new feature** — out of audit scope.
- **Directory `snapshot_id` filter is a documented no-op** (outer-join path). Left as-is per
  its inline comment; changing it is a design decision, not a bug fix.

---

## Validation Results

### Backend
```
ruff check app tests   → All checks passed!
black --check app tests → 80 files unchanged
mypy app               → Success: no issues found in 55 source files
pytest                 → 647 passed, 2 warnings
```

### Frontend
```
pnpm test       → 23 passed (4 files)
pnpm lint       → 0 errors, 0 warnings
pnpm typecheck  → 0 errors
pnpm build      → compiled, 15 routes
```

All gates green after every fix (validated incrementally, not just at the end).

---

## Remaining Cloud Blockers

These are the only outstanding Phase 7 tasks; each requires credentials the audit cannot
provide:

| Task | Blocker |
|------|---------|
| **P7.3** — Seed demo DB with synthetic data; verify every page + filter | Supabase project + Railway backend (P0.8–P0.11). Synthetic data is generated and ready at `data/synthetic/`. |
| **P7.5** — README screenshots / GIFs / live demo link | Requires P7.3 (a live, seeded deployment to capture). |
| **P7.9** — Production deploy (CORS lock-down, secrets, migration-on-deploy) | Supabase + Railway + Vercel accounts. |

---

## Overall Project Readiness

**~92% complete.**

- All code, tests, and documentation for the 6 unblocked Phase 7 tasks are complete and
  validated. The country-filter correctness bug — the only functional defect found — is fixed.
- The remaining ~8% is entirely cloud-dependent (seed a live DB, deploy, capture screenshots).
  No further code work is possible or advisable until Supabase / Railway / Vercel credentials
  are provided.

**Recommended next step:** Provision the three cloud accounts, then run the P7.3 seed workflow
from `docs/CURATOR_RUNBOOK.md` using `data/synthetic/synthetic_alumni_2025_Q1.csv` and `_Q2.csv`.
