# FTMM Alumni Intelligence Dashboard

A centralized **analytics & reporting** dashboard for FTMM (Fakultas Teknologi Maju dan
Multidisiplin), Universitas Airlangga. It consolidates fragmented alumni career data into a
single source of truth and answers where alumni work, what roles/seniority they hold, which
companies/industries employ them, where they are located, and how this varies by study program.

> **Scope:** analytics & reporting only. See the explicit non-goals below.

## Tech stack

| Layer | Choice |
|------|--------|
| Frontend | Next.js (App Router) + TypeScript + TailwindCSS + Shadcn UI + ECharts |
| Backend | FastAPI + SQLAlchemy + Alembic |
| Database | PostgreSQL on Supabase |
| Auth | Supabase Auth (authentication) + app-DB RBAC (authorization) |
| Deploy | Frontend → Vercel · Backend → Railway · DB/Auth → Supabase |

## Monorepo layout (D-037)

```
.
├─ frontend/nextjs-app/      # Next.js App Router frontend
├─ backend/fastapi-app/      # FastAPI single business-logic gateway
├─ database/
│  ├─ migrations/            # pointer to canonical Alembic versions
│  └─ schema/                # schema docs / future ERD
├─ docs/
│  ├─ prd/                   # product requirements
│  ├─ architecture/          # context, readiness, scope lock, roadmap, risks
│  └─ decisions/             # DECISIONS.md (D-001–D-051) — the contract
└─ scripts/
   ├─ imports/               # import CLIs (later phases)
   └─ maintenance/           # maintenance / synthetic-data tooling (later phases)
```

> **Canonical migrations** live under `backend/fastapi-app/migrations/` (Alembic).
> `database/migrations/` holds a pointer so the `database/` epic stays discoverable.

## Governance docs

The project is built strictly to its written contract:

- [docs/CLAUDE_CODE_HANDOFF.md](docs/CLAUDE_CODE_HANDOFF.md) — single-source implementation briefing.
- [docs/decisions/DECISIONS.md](docs/decisions/DECISIONS.md) — decisions D-001–D-051 (authoritative).
- [docs/architecture/IMPLEMENTATION_ROADMAP.md](docs/architecture/IMPLEMENTATION_ROADMAP.md) — phased roadmap.
- [docs/architecture/PROJECT_CONTEXT.md](docs/architecture/PROJECT_CONTEXT.md) — product context.
- [docs/PHASE0_EXECUTION_PLAN.md](docs/PHASE0_EXECUTION_PLAN.md) — current phase plan.

## Permanent non-goals (never built)

No AI/LLM/chatbot/RAG, no recommendation or confidence-scoring or predictive analytics, no
AI/ML/fuzzy matching, no real-time sync/streaming, no microservices/event-driven/Kafka/CQRS,
no Kubernetes/distributed systems. All matching, validation, and deduplication are
**deterministic and curator-controlled**. Only `validated` alumni appear in analytics;
employment is reported as **"Employed vs Not Reported"** (never an asserted unemployment rate).
Development uses **synthetic data only** until legal preconditions (R-001/R-002) clear.

## Local development

See per-app instructions:

- Backend: [backend/fastapi-app/README.md](backend/fastapi-app/README.md)
- Frontend: [frontend/nextjs-app/README.md](frontend/nextjs-app/README.md)

Quick start (from repo root):

```bash
# Backend
cd backend/fastapi-app
uv sync
cp .env.example .env            # fill in values
uv run uvicorn app.main:app --reload --port 8000   # GET http://localhost:8000/health

# Frontend (separate terminal)
cd frontend/nextjs-app
pnpm install
cp .env.example .env.local      # fill in values
pnpm dev                        # http://localhost:3000
```

## Project status

**Phase 0 — Foundations & Infrastructure Bootstrap.** An empty but deployable skeleton across
Vercel + Railway + Supabase, with CI. No database models, auth, or dashboards yet — those arrive
in later phases per the roadmap.
