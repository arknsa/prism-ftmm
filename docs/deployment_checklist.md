# Production Deployment Checklist — PRISM (H3 R1)

Companion to `production_deployment_runbook.md`. Work top to bottom; do not skip the
smoke-test gate. Items flagged **[BLOCKER]** must be cleared before go-live.

## 1. Pre-deployment
- [ ] Target commit merged; working tree clean; release commit/tag noted.
- [ ] Backend suite green (`pytest` → 689 passed, 54 skipped) and integration green with `TEST_DATABASE_URL`.
- [ ] Frontend green (`pnpm build`, `pnpm lint`, `pnpm test` → 23/23).
- [ ] Production domains decided: Railway `https://<svc>.up.railway.app`, Vercel `https://<project>.vercel.app`.
- [ ] Secrets in hand: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` (stored in a secret manager, not chat/repo).
- [ ] **[BLOCKER]** Plan to remove the `e2e-admin@ftmm.ac.id` test admin and create the real admin (H1).
- [ ] `alembic current` = `0010`; `seed_rbac.py` and `bootstrap_admin.py` ready to run.
- [ ] Exact CORS origin (the Vercel domain, no trailing slash) written down.

## 2. Railway (backend)
- [ ] Service created from repo; **Root Directory = `backend/fastapi-app`**.
- [ ] Env vars set: `APP_ENV=production`, `DATABASE_URL`, `SUPABASE_URL`, `BACKEND_CORS_ORIGINS`, `SUPABASE_SERVICE_ROLE_KEY`, (`SUPABASE_ANON_KEY` optional), (`LOG_LEVEL=WARNING` optional).
- [ ] `SUPABASE_JWT_SECRET` intentionally **omitted** (ES256/JWKS).
- [ ] Deploy triggered.
- [ ] **[M2]** Build log shows `uv` provisioned; `alembic upgrade head` succeeded; `uvicorn` started (no fail-fast config error).
- [ ] `GET /health` → `200`, `database:"connected"`.
- [ ] `GET /docs` → `404` (disabled in production).
- [ ] Railway production URL recorded.

## 3. Vercel (frontend)
- [ ] Project imported; **Root Directory = `frontend/nextjs-app`**; framework = Next.js (auto).
- [ ] Env vars set for **Production + Preview**: `NEXT_PUBLIC_API_BASE_URL` (= Railway URL), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- [ ] Deploy succeeds (build compiles).
- [ ] Vercel production domain recorded.
- [ ] **[M6]** `BACKEND_CORS_ORIGINS` on Railway exactly equals the Vercel origin (scheme+host, no trailing slash); backend redeployed if it changed.

## 4. Supabase verification
- [ ] `alembic_version = 0010`; 17 domain tables present.
- [ ] RBAC seeded: 4 roles, 14 permissions, 33 mappings (`seed_rbac.py`, idempotent).
- [ ] **[BLOCKER]** Real admin created via `bootstrap_admin.py`; **`e2e-admin@ftmm.ac.id` deleted** (Supabase user + `app_user` row) — H1.
- [ ] Auth → URL Configuration: **Site URL** and **Redirect URLs** include the Vercel domain.
- [ ] Managed backups confirmed enabled.

## 5. Smoke tests (Go/No-Go gate)
**A. Backend**
- [ ] `GET https://<railway>/health` → `200`, `app_env:"production"`, `database:"connected"`.
- [ ] `GET /docs` → `404`.
- [ ] `GET /me` (no token) → `422`/`401` (never `500`).

**B. End-to-end (Supabase sign-in → API)**
- [ ] `/me` → `200`, role `Admin`, **14 permissions** (JWKS/ES256 + RBAC).
- [ ] Analytics all `200`: `overview, filter-options, career-outcomes, companies, industries, geography, directory`.
- [ ] Curator all `200`: `/companies`, `/dedup/candidates`, `/snapshots`, `/alumni?validation_status=pending`.
- [ ] Supabase `sign_out` succeeds.

**C. Browser (Vercel)**
- [ ] Open Vercel URL → redirected to `/login`.
- [ ] Sign in with the real admin → dashboard renders.
- [ ] Nav shows analytics + all curator pages + Admin (RBAC).
- [ ] An analytics page and a curator page load (empty states OK); **no CORS errors** in console.
- [ ] Sign out → `/login`; hitting a protected route redirects to `/login`.

**Gate:** all A–C green ⇒ proceed. Failure signatures — 401 on `/me` → JWKS/`SUPABASE_URL`; CORS console error → `BACKEND_CORS_ORIGINS`; 403 on `/me` → admin not provisioned.

## 6. Rollback
- [ ] **Frontend:** Vercel → promote previous Production deployment (instant, immutable).
- [ ] **Backend:** Railway → redeploy the prior successful deployment.
- [ ] **Env fix:** correct value → redeploy (frontend requires a **rebuild** for `NEXT_PUBLIC_*`).
- [ ] **Database:** frozen at `0010` ⇒ image rollbacks carry **no DB risk**. A future `0011+` reversal is manual (`alembic downgrade -1`), tested-reversible, **data-affecting**, and run deliberately — never via the start command.
- [ ] **Order:** frontend → backend; touch the DB only if a schema change shipped in the same release.

## 7. Post-deployment
- [ ] Real admin login confirmed; admin password rotated from the bootstrap value.
- [ ] All test/verification accounts removed from prod; keys rotated if test tooling used them.
- [ ] Dashboards confirmed showing empty states (no domain data until the first import).
- [ ] Production URLs + secret locations documented; release commit/tag recorded.
- [ ] Uptime monitor added on `/health`; error tracking scheduled (M4).
- [ ] Fast-follows scheduled: `/ready` DB-aware healthcheck (M1), environment separation/staging (M3), observability/alerting (M4), CSP header (M5).
- [ ] First real import planned (curator → Import) to populate analytics.
