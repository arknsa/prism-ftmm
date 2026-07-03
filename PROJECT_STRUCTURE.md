# Project Structure

**FTMM Alumni Intelligence Dashboard — Complete Repository Tree**

Every major folder and file explained. Canonical layout per D-037.

---

```
ftmm-alumni-intelligence-dashboard/
│
├── README.md                         # Project overview, quick-start, phase status table
├── .gitignore                        # Root gitignore: .env, .venv, .next, node_modules, __pycache__
├── .editorconfig                     # Cross-editor consistency (indent, line endings, charset)
├── .pre-commit-config.yaml           # Pre-commit hooks: ruff + black run before every commit
│
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions: backend (ruff+black+mypy+pytest) +
│                                     # frontend (vitest+eslint+prettier+typecheck+build) on PR+main
│
│ ── DECISIONS.md → (see docs/decisions/)
│
├── NEXT_SESSION_HANDOFF.md           # Context doc for resuming development across sessions
├── FINAL_ENGINEERING_AUDIT.md        # Findings + fixes from the repo-wide engineering audit
├── PRODUCTION_READINESS_REPORT.md    # 4 hardening fixes: docs disable, log level, headers, railway.toml
├── PROJECT_COMPLETENESS_REPORT.md    # Cross-check of every planned deliverable vs implementation
├── DEPLOYMENT_GUIDE.md               # Step-by-step operator deploy instructions (12 sections)
├── GO_LIVE_CHECKLIST.md              # 8-section checklist: infra, security, smoke tests, UAT, rollback
├── PORTFOLIO_DEMO_GUIDE.md           # 12-min demo script, resume bullets, interview Q&A
├── PROJECT_FINAL_REPORT.md           # Full project summary (this project's capstone document)
├── PROJECT_STRUCTURE.md              # This file
├── TECHNICAL_DECISIONS_SUMMARY.md    # All D-001–D-051 decisions in concise engineering form
└── INTERVIEW_PREPARATION.md          # 30 interview Q&A pairs across 7 dimensions
│
│
├── backend/
│   └── fastapi-app/                  # Python FastAPI application — the single business-logic gateway
│       │
│       ├── pyproject.toml            # Project metadata + deps + ruff/black/mypy/pytest config
│       ├── uv.lock                   # Locked dependency tree (committed; reproducible installs)
│       ├── alembic.ini               # Alembic config; DB URL is injected at runtime (not here)
│       ├── railway.toml              # Railway deploy config: start cmd (alembic + uvicorn), healthcheck
│       ├── .env.example              # Keys-only env var catalogue (no values committed)
│       │
│       ├── app/                      # Application source
│       │   ├── __init__.py
│       │   ├── main.py               # App factory: create_app(), register routers, CORS, logging
│       │   │                         # OpenAPI docs disabled when APP_ENV=production
│       │   ├── config.py             # Pydantic-settings Settings class; reads from .env / env vars
│       │   │                         # Fields: APP_ENV, LOG_LEVEL, BACKEND_CORS_ORIGINS,
│       │   │                         # DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
│       │   │                         # SUPABASE_JWT_SECRET
│       │   ├── db.py                 # SQLAlchemy engine (lazy, pool_pre_ping), session factory,
│       │   │                         # get_session() FastAPI dependency, ping() for health check
│       │   ├── logging.py            # JsonFormatter: single-line JSON logs to stdout (Railway-native)
│       │   ├── rate_limiting.py      # Sliding-window rate limiter: 10 imports/min/IP, pure Python
│       │   │                         # Exposed as FastAPI Depends for test override
│       │   │
│       │   ├── api/                  # Route handlers (thin layer: validate input → call service → return)
│       │   │   ├── __init__.py
│       │   │   ├── health.py         # GET /health → {status, app_env, database}
│       │   │   ├── me.py             # GET /me → authenticated user's role + permissions
│       │   │   ├── users.py          # GET/POST /users → user provisioning (Admin only)
│       │   │   ├── imports.py        # POST /api/v1/imports (upload CSV/XLSX, stage rows, audit)
│       │   │   │                     # GET /api/v1/imports/{id} (batch summary)
│       │   │   │                     # GET /api/v1/imports/{id}/rows (paginated staged rows)
│       │   │   ├── commit.py         # POST /api/v1/commit (write alumni + career records under snapshot)
│       │   │   │                     # POST /api/v1/alumni/{id}/validate (curator gate)
│       │   │   ├── dedup.py          # GET /api/v1/dedup/candidates (review queue)
│       │   │   │                     # POST /api/v1/dedup/resolve (confirm-merge / keep-separate)
│       │   │   ├── snapshots.py      # GET/POST /api/v1/snapshots (list + create quarter snapshots)
│       │   │   ├── company.py        # GET/PATCH /api/v1/companies (list + edit canonical companies)
│       │   │   │                     # GET/POST /api/v1/companies/{id}/aliases
│       │   │   └── analytics.py      # GET /api/v1/analytics/filter-options
│       │   │                         # GET /api/v1/analytics/overview
│       │   │                         # GET /api/v1/analytics/career-outcomes
│       │   │                         # GET /api/v1/analytics/companies
│       │   │                         # GET /api/v1/analytics/industries
│       │   │                         # GET /api/v1/analytics/geography
│       │   │                         # GET /api/v1/analytics/directory
│       │   │                         # GET /api/v1/analytics/alumni/{id}
│       │   │
│       │   ├── dependencies/         # FastAPI injectable dependencies
│       │   │   ├── __init__.py
│       │   │   ├── auth.py           # verify_jwt() → TokenClaims; get_current_user() → AuthenticatedUser
│       │   │   │                     # JWT verified via SUPABASE_JWT_SECRET (HS256)
│       │   │   │                     # User resolved from app DB by Supabase UUID (D-043)
│       │   │   └── rbac.py           # require_permission(perm) → guard factory
│       │   │                         # Returns a dependency that raises HTTP 403 if perm not in user's set
│       │   │
│       │   ├── models/               # SQLAlchemy ORM models (one file per domain group)
│       │   │   ├── __init__.py       # Imports all models so Alembic autogenerate sees them
│       │   │   ├── reference.py      # StudyProgram, Industry, Location, CaptureSource
│       │   │   ├── company.py        # Company, CompanyAlias
│       │   │   ├── alumni.py         # Alumni (ValidationStatus enum), university field
│       │   │   ├── career.py         # CareerRecord (is_current partial unique index)
│       │   │   ├── snapshot.py       # RefreshSnapshot
│       │   │   ├── security.py       # AppUser, Role, Permission, RolePermission
│       │   │   ├── audit.py          # AuditLog (old_values/new_values JSONB)
│       │   │   ├── staging.py        # ImportBatch, StagingRow
│       │   │   └── dedup.py          # DedupCandidate (Tier-2 queue entries)
│       │   │
│       │   ├── schemas/              # Pydantic v2 request/response schemas
│       │   │   ├── __init__.py
│       │   │   ├── auth.py           # TokenClaims, AuthenticatedUser
│       │   │   ├── me.py             # MeOut
│       │   │   ├── users.py          # UserIn, UserOut
│       │   │   ├── imports.py        # BatchSummary, StagingRowOut, PagedStagingRows
│       │   │   ├── commit.py         # CommitBatchIn, CommitBatchResultOut, ValidateAlumniIn
│       │   │   ├── dedup.py          # DedupCandidateOut, ResolveIn
│       │   │   ├── snapshot.py       # SnapshotIn, SnapshotOut
│       │   │   ├── company.py        # CompanyOut, CompanyPatchIn, AliasIn, AliasOut
│       │   │   └── analytics.py      # OverviewOut, CareerOutcomesOut, FilterOptionsOut, etc.
│       │   │                         # Note: unemployment_rate structurally absent from all schemas
│       │   │
│       │   └── services/             # Business logic (pure functions / classes; never call session.commit)
│       │       ├── __init__.py
│       │       ├── audit.py          # write_audit_entry() — called from route layer after mutations
│       │       ├── import_parser.py  # parse_import(): CSV/XLSX → StagingRows; SUPPORTED_SOURCES
│       │       ├── program_matcher.py # map_program_text() → StudyProgram; 20+ variant aliases
│       │       ├── validation_status.py # assign_validation_status() → pending/validated/rejected
│       │       ├── company_normalization.py # resolve_company() → Company (via alias or new)
│       │       ├── industry_classification.py # attach_industry() → links company to Industry row
│       │       ├── location_normalization.py  # resolve_location() → Location canonical row
│       │       ├── role_seniority.py # classify_seniority() → Junior/Mid/Senior/Lead/Director
│       │       ├── dedup.py          # tier1_match() (linkedin_url exact), tier2_candidates() (key match)
│       │       ├── dedup_queue.py    # confirm_merge(), keep_separate() — curator resolution
│       │       ├── snapshot.py       # create_snapshot(), list_snapshots()
│       │       ├── commit.py         # commit_batch() — writes Alumni + CareerRecord rows under snapshot
│       │       ├── user_provisioning.py # provision_user() — creates AppUser + optional Supabase user
│       │       ├── analytics_filters.py # AnalyticsFilters dataclass; build_alumni_where();
│       │       │                        # build_career_where(); build_country_clause() (IN subquery)
│       │       └── analytics.py      # get_overview(), get_career_outcomes(), get_company_analytics(),
│       │                             # get_industry_analytics(), get_geographic_analytics(),
│       │                             # get_alumni_directory(), get_alumnus_detail(), get_filter_options()
│       │
│       ├── migrations/               # Alembic migration tree (canonical; database/migrations/ is a pointer)
│       │   ├── env.py                # Reads DATABASE_URL from settings; imports all models for autogenerate
│       │   ├── script.py.mako        # Migration file template
│       │   └── versions/
│       │       ├── 0001_baseline.py          # Empty baseline (schema starts here)
│       │       ├── 0002_reference_tables.py  # StudyProgram, Industry, Location, CaptureSource
│       │       ├── 0003_refresh_snapshot.py  # RefreshSnapshot
│       │       ├── 0004_security_tables.py   # AppUser, Role, Permission, RolePermission
│       │       ├── 0005_company.py           # Company, CompanyAlias
│       │       ├── 0006_alumni.py            # Alumni (with validation_status enum, university, source_id)
│       │       ├── 0007_audit_log.py         # AuditLog (JSONB columns)
│       │       ├── 0008_career_record_indexes_constraints.py  # CareerRecord + all indexes
│       │       └── 0009_staging_tables.py    # ImportBatch, StagingRow, DedupCandidate
│       │
│       └── tests/                    # 647 pytest tests (24 files)
│           ├── conftest.py           # Shared fixtures: in-memory SQLite engine, seeded session,
│           │                         # test FastAPI app factory with dependency overrides
│           ├── test_health.py                   #   1 test
│           ├── test_audit_service.py            #   6 tests
│           ├── test_rate_limiting.py            #   6 tests
│           ├── test_import_atomicity.py         #   7 tests
│           ├── test_validation_status.py        #  15 tests
│           ├── test_industry_classification.py  #  13 tests
│           ├── test_user_provisioning.py        #  18 tests
│           ├── test_me_endpoint.py              #  17 tests
│           ├── test_users_endpoint.py           #  19 tests
│           ├── test_dedup_queue.py              #  22 tests
│           ├── test_auth_dependencies.py        #  24 tests
│           ├── test_company_api.py              #  25 tests
│           ├── test_company_normalization.py    #  25 tests
│           ├── test_snapshot.py                 #  35 tests
│           ├── test_import_parser.py            #  34 tests
│           ├── test_program_matcher.py          #  35 tests
│           ├── test_imports_endpoint.py         #  32 tests
│           ├── test_location_normalization.py   #  29 tests
│           ├── test_commit.py                   #  40 tests
│           ├── test_dedup.py                    #  52 tests
│           ├── test_analytics.py                #  41 tests
│           ├── test_aggregation_edge_cases.py   #  31 tests
│           ├── test_quarterly_e2e.py            #  29 tests
│           └── test_role_seniority.py           #  91 tests
│                                                # ─────────
│                                                #  647 total
│
│
├── frontend/
│   └── nextjs-app/                   # Next.js 16 App Router frontend
│       │
│       ├── package.json              # Scripts: dev, build, start, lint, typecheck, test, format
│       ├── pnpm-lock.yaml            # Locked dependency tree
│       ├── tsconfig.json             # TypeScript config; path alias @/ → project root
│       ├── next.config.ts            # Security headers (5 OWASP), no other config needed
│       ├── tailwind.config.ts        # TailwindCSS v4 config
│       ├── components.json           # Shadcn UI config (component registry settings)
│       ├── vitest.config.ts          # Vitest: happy-dom env, @/ alias, __tests__/** glob, globals:false
│       ├── eslint.config.mjs         # ESLint flat config: next/core-web-vitals + typescript
│       ├── prettier.config.mjs       # Prettier config with tailwindcss plugin
│       ├── .env.example              # Keys-only: NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_SUPABASE_*
│       │
│       ├── app/                      # Next.js App Router pages (file-system routing)
│       │   ├── layout.tsx            # Root layout: HTML, font, AuthProvider wrapper
│       │   │
│       │   ├── (auth)/               # Route group: unauthenticated pages (no nav/shell)
│       │   │   └── login/
│       │   │       ├── page.tsx      # Login page shell
│       │   │       └── login-form.tsx # Email+password form; calls Supabase Auth signIn
│       │   │
│       │   └── (dashboard)/          # Route group: authenticated pages (nav + filter bar)
│       │       ├── layout.tsx        # Dashboard layout: auth guard, nav, filter bar, page-shell
│       │       ├── page.tsx          # / → Overview: 4 KPIs + alumni-by-program bar chart
│       │       ├── careers/
│       │       │   └── page.tsx      # /careers → Career Outcomes: employed split + seniority
│       │       ├── companies/
│       │       │   └── page.tsx      # /companies → Top Employers ranked list
│       │       ├── industries/
│       │       │   └── page.tsx      # /industries → Industry + sector breakdown
│       │       ├── geography/
│       │       │   └── page.tsx      # /geography → Country + city distribution
│       │       ├── directory/
│       │       │   ├── page.tsx      # /directory → Searchable, paginated alumni table
│       │       │   └── [id]/
│       │       │       └── page.tsx  # /directory/[id] → Alumnus profile + career history
│       │       ├── curator/
│       │       │   ├── import/
│       │       │   │   └── page.tsx  # /curator/import → File upload, batch summary, row review
│       │       │   ├── validation/
│       │       │   │   └── page.tsx  # /curator/validation → Pending alumni list, validate/reject
│       │       │   ├── dedup/
│       │       │   │   └── page.tsx  # /curator/dedup → Candidate pairs, confirm-merge / keep-separate
│       │       │   ├── companies/
│       │       │   │   └── page.tsx  # /curator/companies ("Employers") → Alias management
│       │       │   └── snapshots/
│       │       │       └── page.tsx  # /curator/snapshots → Open quarter, view batches, finalize
│       │       └── admin/
│       │           └── page.tsx      # /admin → Admin panel (user management, audit log)
│       │
│       ├── components/               # Shared React components
│       │   ├── ui/
│       │   │   └── button.tsx        # Shadcn Button primitive (base for all buttons)
│       │   ├── nav.tsx               # Role-conditional navigation sidebar/header
│       │   │                         # Curator section: "Employers" link (not "Companies") to avoid
│       │   │                         # label collision with analytics /companies page
│       │   ├── filter-bar.tsx        # Global filter bar: 6 dimensions + Snapshot Quarter switcher
│       │   │                         # Bound to FilterContext; fetches options from filter-options API
│       │   ├── charts.tsx            # Reusable ECharts wrappers: bar, pie/donut, ranked list, geo
│       │   ├── page-shell.tsx        # Consistent page layout with loading / empty / error states
│       │   └── unauthorized.tsx      # 403 state component shown when permission is insufficient
│       │
│       ├── lib/                      # Client-side library modules
│       │   ├── api-client.ts         # apiFetch() typed wrapper; parses {detail} from non-2xx;
│       │   │                         # ApiError class with status + message; getMe(), analytics hooks
│       │   ├── auth-context.tsx      # AuthProvider + useAuth(): user state, 401 → signOut + redirect
│       │   ├── filter-context.tsx    # FilterProvider + useFilters(): setFilter, clearFilters,
│       │   │                         # toQueryParams(); drives all analytics pages
│       │   ├── use-analytics.ts      # Data-fetching hooks for each analytics endpoint
│       │   ├── supabase/
│       │   │   ├── client.ts         # getSupabaseBrowserClient() — client-side Supabase instance
│       │   │   └── server.ts         # getSupabaseServerClient() — server-side (RSC/route handlers)
│       │   └── utils.ts              # cn() — tailwind-merge + clsx utility
│       │
│       └── __tests__/                # Vitest test suite (23 tests, 4 files)
│           ├── setup.ts              # Test setup: @testing-library/react cleanup
│           └── lib/
│               ├── api-client.test.ts        #  8 tests: ApiError shape, apiFetch network/detail/success
│               ├── auth-context.test.tsx     #  3 tests: 401→redirect, success→user, 500→no redirect
│               ├── filter-context.test.tsx   #  6 tests: initial state, setFilter, toQueryParams, clear
│               └── build-query-string.test.ts #  6 tests: empty, encoding, null omission
│
│
├── database/
│   ├── migrations/
│   │   └── README.md                 # Pointer: canonical migrations live in backend/fastapi-app/migrations/
│   └── schema/
│       └── .gitkeep                  # Placeholder; detailed schema docs live in docs/architecture/ER_DIAGRAM.md
│
│
├── data/
│   └── synthetic/                    # Synthetic alumni datasets (no PII — D-050/D-051)
│       ├── synthetic_alumni_2025_Q1.csv  # 100 alumni across 5 FTMM programs (seed 42)
│       └── synthetic_alumni_2025_Q2.csv  # 120 alumni: Q1 carry-forward + 20 new graduates
│
│
├── scripts/
│   ├── imports/                      # One-time seed + utility scripts (run against live DB)
│   │   ├── _utils.py                 # Shared helpers: DB session factory, env loading
│   │   ├── __init__.py
│   │   ├── seed_study_programs.py    # Inserts the 5 approved FTMM programs (is_ftmm_valid=true)
│   │   ├── seed_capture_sources.py   # Inserts LinkedIn, Verified Faculty Record, Tracer Study sources
│   │   ├── seed_industry.py          # Inserts industry taxonomy (industry_name + sector_name)
│   │   ├── seed_location.py          # Inserts canonical location reference data
│   │   ├── seed_rbac.py              # Inserts 4 roles, 12 permissions, 38 role-permission assignments
│   │   └── run_import.py             # CLI entry point: import a CSV file + provision-user subcommand
│   └── maintenance/
│       └── generate_synthetic_data.py # Generates reproducible synthetic alumni CSVs
│                                      # --output-dir data/synthetic --seed 42
│                                      # Produces Q1 (100 rows) + Q2 (120 rows)
│
│
└── docs/
    ├── PHASE0_EXECUTION_PLAN.md      # Detailed Phase 0 task specs (the only per-phase plan file)
    ├── CLAUDE_CODE_HANDOFF.md        # Full project briefing for the implementation agent
    ├── CURATOR_RUNBOOK.md            # Step-by-step quarterly refresh guide for data curators
    │                                 # Steps 1–7: Snapshot → Import → Review → Commit → Dedup → Validate → Verify
    │
    ├── architecture/
    │   ├── IMPLEMENTATION_ROADMAP.md     # 79-task phased roadmap (P0.1–P7.9) with dependencies
    │   ├── ER_DIAGRAM.md                 # Mermaid ERD for all 16 tables; authoritative schema reference
    │   ├── ROLE_PERMISSION_MATRIX.md     # Concrete permission mapping for all 4 roles (12 permissions)
    │   ├── ENV_AND_SECRETS.md            # Secrets catalogue; per-platform assignment; rotation procedure
    │   ├── PROJECT_CONTEXT.md            # Product context, stakeholder needs, success metrics
    │   ├── ARCHITECTURE_READINESS_REPORT.md  # Architecture review findings (pre-implementation)
    │   ├── MVP_SCOPE_LOCK.md             # Locked MVP scope; explicit exclusions
    │   ├── RISKS.md                      # Risk register with status (R-001–R-020)
    │   └── OPEN_QUESTIONS.md             # Resolved questions log (all closed by D-040–D-051)
    │
    └── decisions/
        ├── DECISIONS.md                  # 51 architectural decisions D-001–D-051 (authoritative)
        ├── BLOCKER_RESOLUTION_PROPOSAL.md # How blockers were resolved before D-040–D-051 were added
        ├── IMPORT_FILE_FORMAT_SPEC.md     # CSV/XLSX column spec for each source type
        ├── CURATION_API_OUTLINE.md        # API contract for the curation endpoints (EP-1–EP-8)
        ├── SENIORITY_LADDER_SPEC.md       # Deterministic seniority rules (91 test cases)
        ├── ROLE_NORMALIZATION_SPEC.md     # Role title normalization rules
        ├── PROGRAM_VARIANT_MAP_SPEC.md    # Program name variant → canonical mapping (20+ aliases)
        └── GEOGRAPHIC_CANONICAL_SPEC.md   # Location canonical value reference
```

---

## Folder Purpose Summary

| Folder | Purpose |
|--------|---------|
| `.github/workflows/` | CI pipeline — all quality gates must pass before merge |
| `backend/fastapi-app/app/api/` | Route handlers: thin, delegate to services, own the transaction |
| `backend/fastapi-app/app/dependencies/` | FastAPI injectable dependencies: auth + RBAC |
| `backend/fastapi-app/app/models/` | SQLAlchemy ORM models: one file per domain group |
| `backend/fastapi-app/app/schemas/` | Pydantic v2 I/O contracts: shapes that cross the API boundary |
| `backend/fastapi-app/app/services/` | Business logic: pure, testable, never call session.commit() |
| `backend/fastapi-app/migrations/versions/` | Alembic migrations: the schema history in code |
| `backend/fastapi-app/tests/` | 647 pytest tests: the data engine is the most tested layer |
| `frontend/nextjs-app/app/(auth)/` | Unauthenticated route group: login only |
| `frontend/nextjs-app/app/(dashboard)/` | Authenticated route group: analytics + curator + admin |
| `frontend/nextjs-app/components/` | Shared React components: charts, nav, filter bar, page shell |
| `frontend/nextjs-app/lib/` | Client logic: API client, auth context, filter context, analytics hooks |
| `frontend/nextjs-app/__tests__/` | 23 vitest tests: API client, auth context, filter context, query builder |
| `database/migrations/` | Pointer only — canonical migrations are in `backend/fastapi-app/migrations/` |
| `data/synthetic/` | Synthetic CSV files for demo/dev — no real PII (D-050/D-051) |
| `scripts/imports/` | One-time seed scripts: RBAC, programs, sources, industries, locations |
| `scripts/maintenance/` | Ongoing utilities: synthetic data generator |
| `docs/architecture/` | Architecture artifacts: roadmap, ERD, role matrix, env guide, risks |
| `docs/decisions/` | Decision records + specs: the authoritative scope contract |
