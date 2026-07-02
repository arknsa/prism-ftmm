# Frontend — Next.js

App Router frontend for the FTMM Alumni Intelligence Dashboard. Phase 0 is a deployable shell
that fetches backend `/health` through the typed API client. The frontend never touches the
database directly (D-031) — all data flows through FastAPI.

## Stack

Next.js (App Router) · TypeScript · TailwindCSS v4 · Shadcn UI · ECharts (installed, unused in Phase 0).

## Requirements

- Node.js 20+
- [pnpm](https://pnpm.io/)

## Setup & run

```bash
cd frontend/nextjs-app
pnpm install
cp .env.example .env.local    # set NEXT_PUBLIC_API_BASE_URL (e.g. http://localhost:8000)

pnpm dev                      # http://localhost:3000
```

The home page shows the live backend health result. If the backend is not running it shows a
graceful "Backend unreachable" state.

## Quality gates

```bash
pnpm lint           # eslint, zero warnings
pnpm typecheck      # tsc --noEmit
pnpm format:check   # prettier
pnpm build          # production build
```

## Env vars

See [.env.example](.env.example). `NEXT_PUBLIC_*` values are browser-exposed by design and set
per platform (Vercel) per D-035.
