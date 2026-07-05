# Production Deployment Runbook — PRISM (H3 R1)

End-to-end runbook to deploy the FTMM Alumni Intelligence Dashboard to production:
**Supabase** (DB + Auth, already provisioned), **Railway** (FastAPI backend),
**Vercel** (Next.js frontend). Companion detail docs: `deployment_railway.md`,
`deployment_vercel.md`.

**Architecture recap:** the frontend authenticates directly against Supabase (ES256
JWT); it calls the backend with that JWT as a Bearer token; the backend verifies the
token via Supabase **JWKS** and resolves authorization from the app DB (D-043). The
frontend never touches the DB directly (D-031).

---

## 0. Prerequisites

- Repo access; Supabase project (ref `bbzlvlmfejivuviwlair`) with the schema migrated to
  `alembic_version = 0010`.
- Secrets in hand: `DATABASE_URL` (session pooler), `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` (publishable).
- Decide the production domains up front (they can be set before first deploy):
  - Backend (Railway): `https://<service>.up.railway.app`
  - Frontend (Vercel): `https://<project>.vercel.app`
- Local tools only for seeding: `uv` (backend venv).

---

## 1. Deployment order (and why)

```
Supabase (verify + seed)  →  Railway backend  →  Vercel frontend  →  reconcile CORS + Auth URLs  →  smoke tests
```

Rationale: the frontend needs the backend URL, and the backend's CORS needs the frontend
origin (a two-way dependency). Resolve it by choosing the Vercel production domain in
advance and setting `BACKEND_CORS_ORIGINS` to it during the Railway step; then reconcile if
the actual Vercel domain differs.

---

## 2. Phase 1 — Supabase (verify + seed)

1. **Verify schema** is at head:
   ```bash
   # from backend/fastapi-app, DATABASE_URL in env
   uv run alembic current      # → 0010 (head)  (or run `alembic upgrade head`)
   ```
2. **Seed RBAC** (idempotent — roles, permissions, mappings):
   ```bash
   DATABASE_URL=... uv run python ../../scripts/imports/seed_rbac.py
   # → "4 role(s), 14 permission(s), 33 mapping(s) inserted (0 each = already seeded)."
   ```
3. **Create the first admin** (Supabase Auth user + APP_USER → Admin role):
   ```bash
   DATABASE_URL=... SUPABASE_URL=https://<ref>.supabase.co \
   SUPABASE_SERVICE_ROLE_KEY=... \
   ADMIN_EMAIL=admin@ftmm.ac.id ADMIN_PASSWORD='<strong>' \
     uv run python ../../scripts/imports/bootstrap_admin.py
   ```
   > A user can log in only if present in **both** Supabase Auth **and** `app_user`. Do this
   > before smoke-testing. (Remove/rotate any earlier `e2e-admin@ftmm.ac.id` test account.)
4. **Auth URL config** (Supabase → Authentication → URL Configuration): set **Site URL** to
   the Vercel production URL and add it to **Redirect URLs** (email links). Do after the
   Vercel domain is known (Phase 4) or set to the predetermined domain now.

---

## 3. Phase 2 — Railway (backend)

1. New service from the repo; **Root Directory = `backend/fastapi-app`** (so Nixpacks sees
   `pyproject.toml`/`railway.toml` and provisions `uv`).
2. Set environment variables:

   | Variable | Value |
   |----------|-------|
   | `APP_ENV` | `production` |
   | `DATABASE_URL` | Supabase pooler URI |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` (JWKS auth) |
   | `BACKEND_CORS_ORIGINS` | the Vercel prod origin, e.g. `https://<project>.vercel.app` |
   | `SUPABASE_SERVICE_ROLE_KEY` | for user-provisioning endpoints |
   | `SUPABASE_ANON_KEY` | (optional; backend `/auth/login` proxy only) |
   | `LOG_LEVEL` | `WARNING` (optional) |

   `SUPABASE_JWT_SECRET` is **not** required (ES256/JWKS). `PORT` is injected by Railway.
3. **Deploy.** `railway.toml` runs `alembic upgrade head` then `uvicorn`. In production the
   app **fails fast** at boot if `DATABASE_URL` or `SUPABASE_URL` is missing.
4. **Verify** (see Smoke tests §6.A): `GET /health` → `200`, `database:"connected"`; `/docs`
   → disabled (404).
5. **First-deploy check:** confirm the Nixpacks build provisioned `uv` (if the start command
   fails on `uv: not found`, add a Nixpacks provider hint and redeploy).

---

## 4. Phase 3 — Vercel (frontend)

1. Import the repo; **Root Directory = `frontend/nextjs-app`**; framework auto-detected
   (Next.js), install/build via `pnpm`.
2. Set environment variables (Production + Preview) — `NEXT_PUBLIC_*` are **inlined at build
   time**, so set them before building:

   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_API_BASE_URL` | the Railway backend URL from Phase 2 |
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase publishable/anon key |

3. **Deploy.** Note the actual production domain.

---

## 5. Phase 4 — Reconcile cross-service

1. If the actual Vercel domain differs from what was set in `BACKEND_CORS_ORIGINS`, update it
   on Railway and redeploy/restart the backend.
2. Confirm Supabase **Site URL / Redirect URLs** include the Vercel domain (Phase 1.4).
3. A `NEXT_PUBLIC_*` change requires a **Vercel redeploy** (build-time inlined).

---

## 6. Smoke tests

### A. Backend (Railway)
```bash
curl -s https://<railway>/health          # → {"status":"ok","app_env":"production","database":"connected"}
curl -s -o /dev/null -w "%{http_code}\n" https://<railway>/docs   # → 404 (docs disabled)
curl -s -o /dev/null -w "%{http_code}\n" https://<railway>/me     # → 422/401 (no token) — never 500
```

### B. End-to-end auth + data (mirrors the R1 verification)
Sign in via Supabase to mint an ES256 token, then exercise the endpoints the pages use:
- `GET /me` → `200`, role `Admin`, **14 permissions** (JWT/JWKS validation + RBAC resolution).
- Analytics (all `200`): `/api/v1/analytics/{overview,filter-options,career-outcomes,companies,industries,geography,directory}`.
- Curator (all `200`): `/api/v1/companies`, `/api/v1/dedup/candidates`, `/api/v1/snapshots`, `/api/v1/alumni?validation_status=pending`.
- Supabase `sign_out` succeeds.

### C. Frontend (Vercel) — browser
1. Open the Vercel URL → redirected to `/login`.
2. Sign in with the seeded admin → redirected to `/` (dashboard renders).
3. Nav shows analytics + all curator pages + Admin (RBAC from `/me`).
4. Open an analytics page and a curator page → data loads (empty states are OK until an
   import runs). No CORS errors in the console (confirms `BACKEND_CORS_ORIGINS`).
5. **Sign out** → back to `/login`; protected routes redirect to `/login`.

**Go/No-Go:** all of §6.A–C green ⇒ deployment healthy. Any 401 on `/me` ⇒ JWKS/`SUPABASE_URL`
issue; CORS console error ⇒ `BACKEND_CORS_ORIGINS`; 403 on `/me` ⇒ admin not provisioned
(Phase 1.3).

---

## 7. Rollback procedures

### Frontend (Vercel)
- **Instant Rollback:** Vercel keeps immutable deployments — in the dashboard, promote the
  previous Production deployment. No rebuild needed.
- Env var mistake: correct the value → **redeploy** (required, since `NEXT_PUBLIC_*` is
  build-time inlined).

### Backend (Railway)
- **Redeploy previous:** in the Railway dashboard, redeploy the prior successful deployment
  (rolls back the image/commit).
- Env var mistake: revert the value → redeploy. A missing required var will fail fast at
  boot (clear `RuntimeError`), and Railway restarts per policy.

### Database / migrations
- The current chain is **frozen at `0010`** and already applied, so normal rollbacks
  (frontend/backend image) carry **no DB risk**.
- If a *future* migration (`0011+`) is shipped and must be reversed: the chain is
  reversible (`downgrade` is tested), but it is **manual and data-affecting** — run
  `uv run alembic downgrade -1` against the DB deliberately, not via the start command, and
  only after assessing data impact. Rolling back the backend image alone does **not** undo an
  applied migration.

### Order for a full rollback
Frontend → backend (both to prior deployments). Touch the DB only if a schema change was
shipped in the same release.

---

## 8. Post-deploy

- Remove/rotate the `e2e-admin@ftmm.ac.id` test account; keep the real admin created in
  Phase 1.3 (change its password).
- No domain data exists yet — dashboards show empty states until the first import runs
  (curator → Import).
- Known follow-ups (not blockers): observability (correlation-id/metrics), rate-limiting
  hardening for scale, and the audit's remaining MEDIUM items (see
  `production_audit_phase1_phase3.md`).
