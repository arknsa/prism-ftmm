# PHASE0_EXECUTION_PLAN.md

> Execution plan for **Phase 0 — Foundations & Infrastructure Bootstrap** only.
> Source of truth: IMPLEMENTATION_ROADMAP.md (tasks P0.1–P0.12) + DECISIONS.md (D-011–D-014, D-031, D-035, D-037).
> **No application code is produced here** — this is a build plan. File *contents* are described by purpose; the implementation agent writes them in the build step.
> **Goal of Phase 0:** an empty but fully deployable system across Vercel + Railway + Supabase, with CI, so every later phase ships continuously.

---

## Phase 0 readiness check

**Blocking prerequisites for Phase 0:** none. Phase 0 is pure scaffolding/infrastructure and depends on no missing artifact.

**Accounts/access the developer must have ready:** GitHub (repo + Actions), Supabase, Railway, Vercel. (These are operator actions, not code.)

**Artifacts NOT needed for Phase 0 but required before later phases** (flagged so they can be prepared in parallel):
- Consolidated **ER diagram / physical schema** → before Phase 1.
- **Role→permission matrix** (concrete per-role permissions) → before Phase 1 (P1.12).
- **Industry taxonomy standard** + **seniority ladder** definitions → before Phase 3.
- **Validation matcher rule spec** (program-name variant mapping) → before Phase 3 (P3.4).
- **API contract / OpenAPI outline** for curation + aggregation endpoints → before Phases 3/5.
- **Synthetic data spec** → useful from Phase 3 onward.
- **UI wireframes + theme tokens** (colors/typography) → before Phases 4/6 frontend.
- **Legal sign-off R-001/R-002** → before any real PII load (never blocks dev on synthetic data).

---

## Target folder structure at end of Phase 0

```
ftmm-alumni-platform/
├─ README.md
├─ .gitignore
├─ .editorconfig
├─ .pre-commit-config.yaml
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ docs/
│  ├─ prd/
│  ├─ architecture/
│  │  ├─ PROJECT_CONTEXT.md
│  │  ├─ ARCHITECTURE_READINESS_REPORT.md
│  │  └─ MVP_SCOPE_LOCK.md
│  └─ decisions/
│     └─ DECISIONS.md
├─ backend/
│  └─ fastapi-app/
│     ├─ pyproject.toml
│     ├─ alembic.ini
│     ├─ app/
│     │  ├─ __init__.py
│     │  ├─ main.py            # app factory + router include
│     │  ├─ config.py          # settings from env
│     │  ├─ logging.py         # structured logging setup
│     │  ├─ db.py              # SQLAlchemy engine/session (Supabase pooler)
│     │  └─ api/
│     │     └─ health.py       # GET /health
│     ├─ migrations/           # alembic env + versions (empty)
│     └─ tests/
│        └─ test_health.py
├─ frontend/
│  └─ nextjs-app/
│     ├─ package.json
│     ├─ tsconfig.json
│     ├─ next.config.ts
│     ├─ tailwind.config.ts
│     ├─ components.json        # shadcn config
│     ├─ app/
│     │  ├─ layout.tsx          # root layout + theme
│     │  └─ page.tsx            # placeholder home calling /health
│     ├─ lib/
│     │  └─ api-client.ts       # typed fetch wrapper to backend
│     └─ components/ui/         # shadcn primitives
├─ database/
│  ├─ migrations/              # symlink/doc pointer to alembic versions
│  └─ schema/                  # schema docs / future ERD
└─ scripts/
   ├─ imports/
   └─ maintenance/
```

> Note: Alembic versions physically live under `backend/fastapi-app/migrations/`; `database/migrations/` holds a pointer/readme so the roadmap's `database/` epic stays discoverable. Pick one as canonical and document it (recommended: alembic dir canonical).

---

## Consolidated environment-variable catalogue (Phase 0)

| Variable | Used by | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | backend | Supabase Postgres connection (use the **pooler** URI). |
| `SUPABASE_URL` | backend, frontend | Supabase project URL. |
| `SUPABASE_ANON_KEY` | frontend | Public client key (auth, later phases). |
| `SUPABASE_SERVICE_ROLE_KEY` | backend | Privileged server key (never exposed to frontend). |
| `SUPABASE_JWT_SECRET` | backend | Verify Supabase-issued JWTs (used Phase 2; set now). |
| `BACKEND_CORS_ORIGINS` | backend | Allowed origins (Vercel URL). |
| `APP_ENV` | backend | `local` / `production`. |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Railway backend base URL. |
| `NEXT_PUBLIC_SUPABASE_URL` | frontend | Mirror of SUPABASE_URL for client. |

> Secrets are set **per platform** (Railway for backend, Vercel for frontend) per D-035; never commit them. Provide a committed `.env.example` in each app with keys only (no values).

---

# Task-by-task execution detail

## P0.1 — Monorepo scaffold  ·  Type: INFRA  ·  Cx: S

- **Objective:** create the approved monorepo skeleton (D-037) so all later work has a home.
- **Deliverables:** root repo with `frontend/`, `backend/`, `database/`, `docs/`, `scripts/` (+ subfolders), and a root `README.md` stub.
- **Files to create:** `README.md`; empty `.gitkeep` files in empty dirs (`docs/prd/`, `database/schema/`, `scripts/imports/`, `scripts/maintenance/`).
- **Folder structure:** the top-level tree shown above (without app internals yet).
- **Required dependencies:** git only.
- **Environment variables:** none.
- **Acceptance criteria:** repo initialized; tree matches D-037 layout; pushes to GitHub; `README.md` names the project and links the docs folder.

## P0.2 — Import finalized docs into `docs/`  ·  Type: DOC  ·  Cx: S

- **Objective:** make the finalized governance docs travel with the code.
- **Deliverables:** PROJECT_CONTEXT, ARCHITECTURE_READINESS_REPORT, MVP_SCOPE_LOCK in `docs/architecture/`; DECISIONS in `docs/decisions/`. (CLAUDE_CODE_HANDOFF.md added at repo root or `docs/`.)
- **Files to create:** copies of the five finalized docs + this plan + handoff.
- **Folder structure:** `docs/architecture/`, `docs/decisions/` populated.
- **Required dependencies:** none.
- **Environment variables:** none.
- **Acceptance criteria:** all governance docs present in `docs/`; links from README resolve.

## P0.3 — Tooling configuration  ·  Type: INFRA  ·  Cx: M

- **Objective:** enforce portfolio-grade consistency from commit #1.
- **Deliverables:** backend Python toolchain (dependency manager + ruff + black + mypy), frontend Node toolchain (pnpm + eslint + prettier), shared `.editorconfig`, root `.gitignore`, pre-commit hooks running formatters/linters.
- **Files to create:** `backend/fastapi-app/pyproject.toml` (deps + tool configs), `frontend/nextjs-app/package.json` + eslint/prettier configs, root `.editorconfig`, root `.gitignore`, `.pre-commit-config.yaml`.
- **Folder structure:** config files at the locations above.
- **Required dependencies:** Python: `ruff`, `black`, `mypy`; Node: `eslint`, `prettier`, `typescript`; `pre-commit`.
- **Environment variables:** none.
- **Acceptance criteria:** `pre-commit run --all-files` passes clean; lint + typecheck commands succeed on the empty skeleton.

## P0.4 — FastAPI app skeleton  ·  Type: BE  ·  Cx: M

- **Objective:** a runnable backend exposing a health check (D-031 single gateway begins here).
- **Deliverables:** app factory, env-driven settings, structured logging, `GET /health` returning status + app env, CORS middleware reading `BACKEND_CORS_ORIGINS` (placeholder origin for now).
- **Files to create:** `app/main.py`, `app/config.py`, `app/logging.py`, `app/api/health.py`, `app/__init__.py`, `backend/.env.example`.
- **Folder structure:** `backend/fastapi-app/app/` with `api/` subpackage.
- **Required dependencies:** `fastapi`, `uvicorn`, `pydantic-settings`.
- **Environment variables:** `APP_ENV`, `BACKEND_CORS_ORIGINS`.
- **Acceptance criteria:** `uvicorn` serves locally; `GET /health` → 200 JSON; CORS configurable; settings load from env; logs are structured.

## P0.5 — SQLAlchemy + Alembic wiring  ·  Type: BE  ·  Cx: M

- **Objective:** DB connectivity + migration framework ready (no models yet).
- **Deliverables:** SQLAlchemy engine/session bound to `DATABASE_URL` (Supabase **pooler**), Alembic initialized and pointed at the app's metadata, an empty baseline migration that runs cleanly.
- **Files to create:** `app/db.py`, `alembic.ini`, `migrations/env.py`, baseline `migrations/versions/*` (empty), update `backend/.env.example`.
- **Folder structure:** `backend/fastapi-app/migrations/`.
- **Required dependencies:** `sqlalchemy`, `alembic`, `psycopg[binary]` (or `psycopg2-binary`).
- **Environment variables:** `DATABASE_URL`.
- **Acceptance criteria:** `alembic upgrade head` connects to Supabase and runs the empty baseline without error; a DB-ping on app startup succeeds.

## P0.6 — Next.js + Tailwind + Shadcn shell  ·  Type: FE  ·  Cx: M

- **Objective:** a deployable frontend shell with the approved design stack (D-011).
- **Deliverables:** Next.js (App Router) + TypeScript project; TailwindCSS configured; Shadcn UI initialized with base theme tokens; root layout; placeholder home page; ECharts dependency installed (unused for now).
- **Files to create:** `package.json`, `tsconfig.json`, `next.config.ts`, `tailwind.config.ts`, `components.json`, `app/layout.tsx`, `app/page.tsx`, base `components/ui/` primitives, `frontend/.env.example`.
- **Folder structure:** `frontend/nextjs-app/app/`, `components/ui/`, `lib/`.
- **Required dependencies:** `next`, `react`, `typescript`, `tailwindcss`, `shadcn-ui` primitives, `echarts` (+ `echarts-for-react` if used).
- **Environment variables:** `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`.
- **Acceptance criteria:** `next dev` renders the shell; Tailwind + a Shadcn component render; theme tokens applied; build succeeds.

## P0.7 — Frontend API client layer  ·  Type: FE  ·  Cx: S

- **Objective:** one typed place for all backend calls (frontend never touches DB — D-031).
- **Deliverables:** a typed fetch wrapper reading `NEXT_PUBLIC_API_BASE_URL`, with error handling and a `getHealth()` example call wired into the home page.
- **Files to create:** `lib/api-client.ts`; minimal update to `app/page.tsx` to display backend health.
- **Folder structure:** `frontend/nextjs-app/lib/`.
- **Required dependencies:** none beyond P0.6.
- **Environment variables:** `NEXT_PUBLIC_API_BASE_URL`.
- **Acceptance criteria:** home page shows live `/health` result fetched through the client wrapper; network errors handled gracefully.

## P0.8 — Supabase project setup  ·  Type: INFRA  ·  Cx: S

- **Objective:** provision managed Postgres + Auth (D-013, D-043).
- **Deliverables:** Supabase project created; Postgres ready; Supabase Auth enabled; connection URI (pooler) + keys captured securely.
- **Files to create:** none (operator action); record key **names** in `.env.example` files.
- **Folder structure:** n/a.
- **Required dependencies:** Supabase account.
- **Environment variables produced:** `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.
- **Acceptance criteria:** can connect to the DB with `DATABASE_URL`; Auth is enabled; keys stored in a secrets manager / platform env, not committed.

## P0.9 — Railway backend deployment  ·  Type: INFRA  ·  Cx: M

- **Objective:** backend live on Railway (D-035).
- **Deliverables:** Railway service building the FastAPI app; env vars set; P0.4 skeleton deployed; public URL; migration-on-deploy hook stubbed.
- **Files to create:** Railway config (e.g., `railway.json`/Procfile-equivalent) or dashboard settings; document the start command.
- **Folder structure:** config at `backend/fastapi-app/`.
- **Required dependencies:** Railway account; P0.4, P0.5, P0.8.
- **Environment variables:** `DATABASE_URL`, `APP_ENV`, `BACKEND_CORS_ORIGINS`, Supabase keys.
- **Acceptance criteria:** deployed `GET /health` returns 200 over the public Railway URL; backend connects to Supabase.

## P0.10 — Vercel frontend deployment  ·  Type: INFRA  ·  Cx: S

- **Objective:** frontend shell live on Vercel (D-035).
- **Deliverables:** Vercel project linked to `frontend/nextjs-app`; env set to the Railway backend URL; shell deployed.
- **Files to create:** Vercel project settings (dashboard) + optional `vercel.json`.
- **Folder structure:** n/a.
- **Required dependencies:** Vercel account; P0.6, P0.9.
- **Environment variables:** `NEXT_PUBLIC_API_BASE_URL` (= Railway URL), `NEXT_PUBLIC_SUPABASE_URL`.
- **Acceptance criteria:** Vercel URL renders the shell; build pipeline green.

## P0.11 — CORS + per-platform secrets strategy  ·  Type: INFRA  ·  Cx: M

- **Objective:** secure cross-service comms and a documented env strategy (accepted-MVP R-008).
- **Deliverables:** backend CORS locked to the Vercel origin; a short `docs/architecture/ENV_AND_SECRETS.md` describing which secrets live where (Railway vs Vercel vs Supabase) and the `.env.example` convention.
- **Files to create:** `docs/architecture/ENV_AND_SECRETS.md`; update `BACKEND_CORS_ORIGINS`.
- **Folder structure:** n/a.
- **Required dependencies:** P0.9, P0.10.
- **Environment variables:** `BACKEND_CORS_ORIGINS` (= Vercel origin).
- **Acceptance criteria:** frontend on Vercel successfully calls backend on Railway (no CORS errors); secrets doc committed; no secret values in git.

## P0.12 — Minimal CI pipeline  ·  Type: INFRA  ·  Cx: M

- **Objective:** continuous quality + deploy gating from day one.
- **Deliverables:** GitHub Actions workflow running lint + typecheck for both apps on PR; deploy trigger on `main` (or documented auto-deploy via Railway/Vercel git integration).
- **Files to create:** `.github/workflows/ci.yml`.
- **Folder structure:** `.github/workflows/`.
- **Required dependencies:** P0.3 (lint/typecheck commands).
- **Environment variables:** CI secrets as needed for deploy (platform tokens).
- **Acceptance criteria:** a PR runs lint + typecheck for backend and frontend and blocks on failure; merging to `main` results in both apps deploying.

---

## Phase 0 exit checklist (Definition of Done)

- [ ] Monorepo matches D-037 layout; governance docs in `docs/`.
- [ ] Tooling: `pre-commit run --all-files` clean; lint + typecheck pass both apps.
- [ ] Backend: `GET /health` 200 locally **and** on Railway; connects to Supabase; `alembic upgrade head` runs the empty baseline.
- [ ] Frontend: shell renders locally **and** on Vercel; home page shows live backend health via the API client.
- [ ] CORS works Vercel↔Railway; no secrets committed; `ENV_AND_SECRETS.md` present.
- [ ] CI green on PR; deploy-on-main verified.

**On completion, proceed to Phase 1 (Database & Reference Data) — but first prepare the ER diagram and role→permission matrix flagged in the readiness check.**
