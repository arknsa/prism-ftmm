# Frontend — Next.js

App Router frontend for the FTMM Alumni Intelligence Dashboard. Renders the analytics dashboard
(15 routes: overview, careers, companies, industries, geography, directory, plus curator/admin
pages) with a global filter bar. Authentication is via Supabase Auth; the frontend never touches
the database directly (D-031) — all data flows through FastAPI.

## Stack

Next.js (App Router) · TypeScript · TailwindCSS v4 · Shadcn UI · ECharts · Supabase Auth.

## Requirements

- Node.js 20+
- [pnpm](https://pnpm.io/)

## Setup & run

```bash
cd frontend/nextjs-app
pnpm install
cp .env.example .env.local    # set NEXT_PUBLIC_API_BASE_URL + Supabase keys

pnpm dev                      # http://localhost:3000
```

Unauthenticated visitors are redirected to `/login`. After sign-in, the dashboard loads the
analytics overview. Analytics pages read from the FastAPI `/api/v1/analytics/*` endpoints.

## Quality gates

```bash
pnpm test           # vitest (23 tests: api-client, filter/auth contexts, query builder)
pnpm lint           # eslint, zero warnings
pnpm typecheck      # tsc --noEmit
pnpm format:check   # prettier
pnpm build          # production build
```

## Env vars

See [.env.example](.env.example). `NEXT_PUBLIC_*` values are browser-exposed by design and set
per platform (Vercel) per D-035.
