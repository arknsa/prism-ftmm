# Frontend Deployment — Vercel

Runbook for deploying the Next.js frontend (`frontend/nextjs-app`) to Vercel. This
is deployment configuration only; no application code changes.

## Build settings

- **Framework:** Next.js (auto-detected). **Root Directory:** `frontend/nextjs-app`
  (set in Vercel Project → Settings → General, since the app lives in a monorepo).
- **Install / build:** Vercel runs `pnpm install` + `pnpm build` from the `pnpm-lock.yaml`.
- Build verified locally: `pnpm build` compiles + typechecks; all 15 routes build
  (dynamic — `force-dynamic` + client-side fetch), `proxy.ts` middleware is recognized.

## Required Vercel environment variables

All are `NEXT_PUBLIC_*` — exposed to the browser **and inlined at build time**, so they
must be set **before** the build (Production and Preview scopes). Changing one requires a
redeploy.

| Variable | Required | Value / purpose |
|----------|:--------:|-----------------|
| `NEXT_PUBLIC_API_BASE_URL` | **Yes** | The Railway backend base URL, e.g. `https://<service>.up.railway.app`. The API client **throws at load in production if unset**. |
| `NEXT_PUBLIC_SUPABASE_URL` | **Yes** | `https://<ref>.supabase.co` — used by the Supabase browser/SSR client for login and session. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | **Yes** | Supabase anon/publishable key. |

(Exactly the three keys documented in `frontend/nextjs-app/.env.example`.)

## Cross-service configuration

- **Backend CORS (Railway):** `BACKEND_CORS_ORIGINS` must include the Vercel origin
  (e.g. `https://your-app.vercel.app`), or browser calls are blocked. The backend allows
  the `Authorization` header (Bearer token) — the frontend authenticates to the API with
  the Supabase access token, not cookies.
- **Supabase Auth URLs:** in Supabase → Authentication → URL Configuration, set **Site URL**
  to the Vercel production URL and add the Vercel domain(s) to **Redirect URLs** (needed for
  email confirmation / password-reset links; password sign-in itself needs no redirect).

## Deployment procedure

1. **Import the repo** into Vercel; set **Root Directory = `frontend/nextjs-app`**.
2. **Set the three env vars** above for Production (and Preview).
3. Ensure the backend is deployed (Railway) and its URL is used for
   `NEXT_PUBLIC_API_BASE_URL`; add the Vercel origin to Railway `BACKEND_CORS_ORIGINS`.
4. **Deploy.** The build inlines the `NEXT_PUBLIC_*` values into the client bundle.
5. **Verify:** open the Vercel URL → redirected to `/login` → sign in with a provisioned
   admin (see `scripts/imports/bootstrap_admin.py`) → dashboard loads and calls the backend
   (`/me`, analytics, curator pages) with the Supabase Bearer token.

## Notes

- Security headers (`X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, etc.) are applied via `next.config.ts`.
- Session refresh runs in `proxy.ts` (Next 16 middleware); the dashboard layout redirects
  unauthenticated users to `/login` server-side.
- A user can log in only if they exist in **both** Supabase Auth **and** `app_user` — seed
  the first admin before demoing (`seed_rbac.py` + `bootstrap_admin.py`).
