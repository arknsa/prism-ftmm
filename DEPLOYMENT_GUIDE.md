# Deployment Guide

**Project:** FTMM Alumni Intelligence Dashboard  
**Stack:** FastAPI (Railway) · Next.js (Vercel) · PostgreSQL (Supabase)  
**Decision reference:** D-035 (deploy mapping), D-043 (auth split), D-031 (single gateway)

---

## Overview

Deploy in this exact order. Each step depends on the previous one.

```
1. Supabase  →  2. Railway  →  3. Verify backend  →  4. Vercel  →  5. CORS lock-down
→  6. Run migrations  →  7. Seed RBAC  →  8. Seed reference data  →  9. Import synthetic data
→  10. Smoke test
```

---

## 1. Supabase Setup

### 1.1 Create the project

1. Go to [supabase.com](https://supabase.com) → **New project**.
2. Choose an organization (or create one).
3. Set a strong **database password** — store it in a password manager. You will not need it directly, but it is part of the connection string.
4. Choose a region closest to your Railway deployment (e.g. Singapore `ap-southeast-1` for Railway's Asia regions).
5. Wait for provisioning (~2 minutes).

### 1.2 Collect credentials

From the Supabase dashboard → **Project Settings** → **API**:

| Key | Where to find it |
|-----|-----------------|
| `SUPABASE_URL` | Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Project Settings → API → Project API Keys → `anon` / `public` |
| `SUPABASE_SERVICE_ROLE_KEY` | Project Settings → API → Project API Keys → `service_role` |
| `SUPABASE_JWT_SECRET` | Project Settings → API → JWT Settings → JWT Secret |

From **Project Settings → Database → Connection String**:
- Select **Transaction pooler** (not Session pooler, not Direct connection).
- Copy the URI. It looks like: `postgresql://postgres.xxxx:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`
- This becomes `DATABASE_URL`. Replace `<password>` with the database password you set in step 1.3.

> **Important:** Use the **Transaction pooler** URI for Railway. The direct connection string does not work with PgBouncer-style pooling that Railway's single-instance deployment expects.

### 1.3 Enable Supabase Auth

In the dashboard → **Authentication** → **Providers**:
- **Email** provider is enabled by default. Leave it enabled.
- No other providers are needed for the MVP.

Under **Authentication → Settings**:
- Set **Site URL** to your Vercel URL (fill in after step 4 — come back to this).
- Set **Redirect URLs** to `https://<your-vercel-app>.vercel.app/**`.

---

## 2. Railway Setup

### 2.1 Create the Railway service

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
2. Connect your GitHub account if not already connected.
3. Select the `ftmm-alumni-intelligence-dashboard` repository.
4. When asked for the root directory, set it to: `backend/fastapi-app`
5. Railway will detect `pyproject.toml` + `uv.lock` and use Nixpacks with uv.

### 2.2 Set environment variables

In Railway → your service → **Variables**, add all of the following:

```
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://postgres.xxxx:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
SUPABASE_JWT_SECRET=<jwt_secret>
BACKEND_CORS_ORIGINS=https://<your-vercel-app>.vercel.app
```

> Leave `BACKEND_CORS_ORIGINS` as a placeholder for now — you will update it after the Vercel deploy in step 4. Railway auto-redeploys when a variable changes.

### 2.3 Confirm the start command

The `railway.toml` in `backend/fastapi-app/` already configures the start command:
```
uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
Railway picks this up automatically. You do not need to set a custom start command in the dashboard.

### 2.4 Configure the healthcheck

`railway.toml` sets `healthcheckPath = "/health"`. Railway will ping this endpoint after deploy. If it does not return HTTP 200 within 30 seconds, the deploy is marked failed and the previous version is kept.

### 2.5 Generate a public Railway URL

In the service settings → **Networking** → **Generate Domain**. Note this URL — it becomes `NEXT_PUBLIC_API_BASE_URL` for Vercel.

---

## 3. Verify Backend

After Railway deploys successfully:

```bash
curl https://<your-railway-app>.railway.app/health
```

Expected response:
```json
{
  "status": "ok",
  "app_env": "production",
  "database": "connected"
}
```

If `"database": "error"` — check `DATABASE_URL` in Railway variables. Common causes: wrong pooler URI format, password not URL-encoded if it contains special characters.

If `"database": "unconfigured"` — `DATABASE_URL` is empty or not set.

> **Note:** `/docs` and `/openapi.json` return 404 in production (disabled when `APP_ENV=production`). This is correct behavior.

---

## 4. Vercel Setup

### 4.1 Create the Vercel project

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → **Import Git Repository**.
2. Select the `ftmm-alumni-intelligence-dashboard` repository.
3. Set **Root Directory** to: `frontend/nextjs-app`
4. Framework Preset: Vercel auto-detects **Next.js**. Accept the default.
5. Do not change Build Command or Output Directory.

### 4.2 Set environment variables

In Vercel → Project → **Settings → Environment Variables**, add:

```
NEXT_PUBLIC_API_BASE_URL=https://<your-railway-app>.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Apply to **Production**, **Preview**, and **Development** environments.

### 4.3 Deploy

Click **Deploy**. Vercel runs `pnpm install && pnpm build`. The build takes 1–3 minutes.

### 4.4 Note your Vercel URL

The default URL is `https://<project-name>.vercel.app`. Note this for the next step.

---

## 5. CORS Lock-Down

Return to Railway → your service → **Variables**. Update:

```
BACKEND_CORS_ORIGINS=https://<your-vercel-app>.vercel.app
```

Railway auto-redeploys. After ~1 minute, the backend accepts requests only from the Vercel origin.

Also return to **Supabase → Authentication → Settings** and set:
- **Site URL**: `https://<your-vercel-app>.vercel.app`
- **Redirect URLs**: `https://<your-vercel-app>.vercel.app/**`

---

## 6. Database Migration

Migrations run **automatically** on every Railway deploy via the `railway.toml` start command (`alembic upgrade head` before uvicorn). You do not need to run them manually.

To verify migrations ran:

```bash
# From backend/fastapi-app, with DATABASE_URL set locally:
uv run alembic current
```

Expected output: `0009_staging_tables (head)` — the most recent migration.

If you ever need to run migrations manually (e.g. from your local machine against the live DB):

```bash
cd backend/fastapi-app
cp .env.example .env          # fill in DATABASE_URL pointing to Supabase
uv run alembic upgrade head
```

---

## 7. RBAC Seed

This creates the 4 roles, all permissions, and the role-permission assignments in the live database. Run once after the first successful migration.

```bash
cd backend/fastapi-app
# Ensure .env contains DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
uv run python ../../scripts/imports/seed_rbac.py
```

Expected output:
```
Seeded 4 roles, 12 permissions, 38 role-permission assignments.
```

The seed script is idempotent — safe to run multiple times. Duplicate-key conflicts are caught and skipped.

---

## 8. Reference Data Seed

Seed the taxonomy tables that the import pipeline depends on. Run in this order:

```bash
cd backend/fastapi-app

# 1. Study programs (5 FTMM programs — D-004)
uv run python ../../scripts/imports/seed_study_programs.py

# 2. Capture sources (LinkedIn, Verified Faculty Record, Tracer Study)
uv run python ../../scripts/imports/seed_capture_sources.py

# 3. Industry reference data (industry_name + sector_name taxonomy)
uv run python ../../scripts/imports/seed_industry.py

# 4. Location reference data (country/province/city canonical values)
uv run python ../../scripts/imports/seed_location.py
```

All four seed scripts are idempotent. Run all four before attempting any data import.

---

## 9. Create the First Admin User

Before the curator can log in, an Admin user must exist. This is a two-step process (D-043: Supabase Auth = authentication, app DB = authorization).

### Step 1 — Create the Supabase Auth user

In the Supabase dashboard → **Authentication → Users → Invite user** (or Add user):
- Email: your admin email (e.g. `admin@ftmm.unair.ac.id`)
- The user receives an invitation email with a link to set their password.

Note the **user UUID** shown in the Users table after creation.

### Step 2 — Provision the app DB record

```bash
cd backend/fastapi-app
uv run python ../../scripts/imports/run_import.py provision-user \
  --supabase-uuid <uuid-from-step-1> \
  --role admin \
  --email admin@ftmm.unair.ac.id
```

This inserts the `APP_USER` row and assigns the Admin role. The admin can now log in at `https://<your-vercel-app>.vercel.app/login`.

---

## 10. Synthetic Data Import (Demo Setup)

Use the curator web UI or the CLI to import the prepared synthetic datasets.

### Option A — Web UI (recommended for demo)

1. Log in as Admin or Data Curator at `/login`.
2. Navigate to **Curator → Snapshots → New Snapshot**.
   - Label: `2025-Q1`, Notes: `Synthetic Q1 dataset`
3. Navigate to **Curator → Import**.
   - Upload `data/synthetic/synthetic_alumni_2025_Q1.csv`
   - Source type: `Tracer Study`
4. Review the batch summary — 100 rows, 0 errors expected.
5. Navigate to **Curator → Validation** — all 100 rows are `pending`.
6. Validate all rows (select all → Validate).
7. Navigate to **Curator → Snapshots** → Finalize (Commit) the Q1 snapshot.
8. Repeat steps 2–7 for Q2: label `2025-Q2`, file `synthetic_alumni_2025_Q2.csv`.

### Option B — CLI

```bash
cd backend/fastapi-app

# Create Q1 snapshot via API
curl -X POST https://<railway-url>/api/v1/snapshots \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"quarter_label": "2025-Q1", "notes": "Synthetic Q1"}'

# Import Q1 CSV
curl -X POST https://<railway-url>/api/v1/imports \
  -H "Authorization: Bearer <admin-jwt>" \
  -F "file=@../../data/synthetic/synthetic_alumni_2025_Q1.csv" \
  -F "source_type=Tracer Study" \
  -F "source_id=3"
```

See `docs/CURATOR_RUNBOOK.md` for the complete step-by-step workflow with all API calls.

---

## 11. Health Verification

After seeding, verify each layer:

```bash
# Backend health
curl https://<railway-url>/health
# Expected: {"status":"ok","app_env":"production","database":"connected"}

# Analytics — overview (requires auth)
curl https://<railway-url>/api/v1/analytics/overview \
  -H "Authorization: Bearer <admin-jwt>"
# Expected: {"total_alumni": N, "total_companies": N, ...}
```

In the Vercel-hosted frontend:
1. Open `https://<your-vercel-app>.vercel.app` → redirects to `/login`.
2. Log in with the admin account.
3. Overview page loads with real aggregates.
4. Change Study Program filter → numbers update.
5. Change Snapshot Quarter → numbers update to the selected quarter's cohort.

---

## 12. Common Deployment Issues

### `"database": "error"` in health check
- **Cause:** `DATABASE_URL` is incorrect or unreachable.
- **Fix:** Verify the pooler URI format: `postgresql://postgres.XXXX:PASSWORD@aws-REGION.pooler.supabase.com:6543/postgres`. Ensure the password does not contain unescaped special characters (URL-encode `@`, `#`, `%`, etc.).

### Railway deploy fails: `alembic upgrade head` error
- **Cause:** `DATABASE_URL` not set yet when the deploy runs.
- **Fix:** Set all environment variables in Railway **before** the first deploy, or trigger a manual redeploy after setting them.

### Vercel build error: `NEXT_PUBLIC_API_BASE_URL` not defined
- **Cause:** env vars set after the build started, or `NEXT_PUBLIC_` prefix missing.
- **Fix:** Verify variables are set with the exact names in Vercel project settings, then trigger a new deployment.

### CORS error in browser console
- **Cause:** `BACKEND_CORS_ORIGINS` does not exactly match the Vercel URL (e.g. trailing slash, wrong subdomain).
- **Fix:** In Railway variables, set `BACKEND_CORS_ORIGINS=https://your-exact-app.vercel.app` (no trailing slash). Railway auto-redeploys.

### Login redirects back to `/login` immediately
- **Cause:** Supabase Auth Site URL / Redirect URL not set to the Vercel domain.
- **Fix:** Supabase dashboard → Authentication → Settings → set Site URL and add Redirect URL to `https://<app>.vercel.app/**`.

### Import fails: `Unknown source_type`
- **Cause:** `source_type` must be exactly one of: `"Tracer Study"`, `"LinkedIn"`, `"Verified Faculty Record"` (case-sensitive).
- **Fix:** Use the exact strings above. Verify `seed_capture_sources.py` ran successfully first.

### `403 Forbidden` on curator endpoints
- **Cause:** Logged-in user does not have the required permission (e.g. `import:run`).
- **Fix:** Verify the user was provisioned with the correct role (`admin` or `data_curator`). Check `APP_USER.role_id` in Supabase table editor.

### Seed script: `UniqueViolation` errors
- All seed scripts are idempotent — they catch duplicate-key conflicts. If you see a `UniqueViolation` that is NOT caught, check that the script version matches the current schema (run `alembic current` to confirm migrations are at head).
