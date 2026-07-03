# Go-Live Checklist

**Project:** FTMM Alumni Intelligence Dashboard  
**Use this checklist** before declaring the deployment production-ready and sharing the URL.  
Work through each section top-to-bottom. Every item must be ✅ before proceeding to the next section.

---

## 1. Infrastructure Checklist

### Supabase
- [ ] Project created in a region matching Railway (reduces latency)
- [ ] Database password stored securely (password manager — not in git)
- [ ] **Transaction pooler** URI captured for `DATABASE_URL` (not Session pooler, not Direct)
- [ ] `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY` all captured
- [ ] Email Auth provider enabled in Supabase dashboard
- [ ] Site URL set to the Vercel domain (`https://<app>.vercel.app`)
- [ ] Redirect URLs set (`https://<app>.vercel.app/**`)
- [ ] (Optional) Daily database backup enabled (Supabase Pro plan → Project Settings → Backups)

### Railway
- [ ] Service created pointing at `backend/fastapi-app` root directory
- [ ] All 7 backend environment variables set (APP_ENV, LOG_LEVEL, DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, BACKEND_CORS_ORIGINS)
- [ ] Public Railway domain generated and noted
- [ ] `railway.toml` detected — start command includes `alembic upgrade head`
- [ ] Healthcheck configured to `/health` (30 s timeout) — Railway shows "Active" after deploy

### Vercel
- [ ] Project created pointing at `frontend/nextjs-app` root directory
- [ ] All 3 frontend environment variables set (NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)
- [ ] Framework preset detected as Next.js automatically
- [ ] Vercel domain noted

### CI / Git
- [ ] GitHub Actions CI passes on `main` branch (backend lint + test + typecheck; frontend test + lint + typecheck + build)
- [ ] No `.env` or `.env.local` files committed to git (`git log --all --name-only | grep ".env$"` returns nothing)

---

## 2. Security Checklist

- [ ] `APP_ENV=production` set on Railway → OpenAPI docs (`/docs`, `/openapi.json`) return 404
  - Verify: `curl https://<railway-url>/docs` → HTTP 404
- [ ] `BACKEND_CORS_ORIGINS` matches the exact Vercel URL (no trailing slash)
  - Verify: open browser DevTools → Network → any API call → Response Headers show `Access-Control-Allow-Origin: https://<app>.vercel.app`
- [ ] `SUPABASE_SERVICE_ROLE_KEY` present only in Railway variables — not in Vercel, not in git
- [ ] `SUPABASE_JWT_SECRET` present only in Railway variables
- [ ] No secret values in any committed file (`.env.example` files contain keys only)
  - Verify: `grep -r "eyJ" . --include="*.env.example"` returns nothing
- [ ] HTTP security headers present on frontend responses:
  - Verify: `curl -I https://<app>.vercel.app` shows `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] Supabase Redirect URL list does not contain `localhost` in production (or is intentionally limited)
- [ ] All analytics endpoints return 401 without a valid JWT
  - Verify: `curl https://<railway-url>/api/v1/analytics/overview` → HTTP 401
- [ ] All curator endpoints return 401/403 without curator-role JWT
  - Verify: `curl https://<railway-url>/api/v1/imports` → HTTP 401

---

## 3. Backend Checklist

- [ ] `GET /health` returns `{"status":"ok","app_env":"production","database":"connected"}`
- [ ] Migration applied: `alembic current` shows `0009_staging_tables (head)`
- [ ] All 9 Alembic migrations applied with no errors in Railway deploy logs
- [ ] RBAC seed completed: 4 roles, 12 permissions, 38 role-permission assignments
- [ ] Reference data seeded:
  - [ ] 5 FTMM study programs in `STUDY_PROGRAM` table (`is_ftmm_valid = true`)
  - [ ] 3 capture sources in `CAPTURE_SOURCE` table (LinkedIn, Verified Faculty Record, Tracer Study)
  - [ ] Industry taxonomy populated in `INDUSTRY` table
  - [ ] Location canonical data populated in `LOCATION` table
- [ ] At least one Admin user provisioned (APP_USER row + Supabase Auth user)
- [ ] Rate limiting active on `/api/v1/imports`: 11th request within 60 s returns HTTP 429
- [ ] Import endpoint rejects files > 10 MB with HTTP 413
- [ ] All 8 analytics endpoints respond with HTTP 200 (with valid JWT + data in DB)

---

## 4. Frontend Checklist

- [ ] `https://<app>.vercel.app` redirects to `/login` (unauthenticated)
- [ ] Login page renders with email + password fields
- [ ] After login, dashboard overview page loads without console errors
- [ ] Navigation shows all 6 analytics pages + curator section (for admin/curator role)
- [ ] Global filter bar is visible on every analytics page
- [ ] All 6 filter dimensions are populated (Study Program, Graduation Year, Industry, Company, Country, Snapshot Quarter)
- [ ] Changing any filter updates the page data
- [ ] All 5 curator pages load:
  - [ ] `/curator/import` — file upload form renders
  - [ ] `/curator/validation` — pending alumni list (or empty state)
  - [ ] `/curator/dedup` — dedup queue (or empty state)
  - [ ] `/curator/companies` — company alias table
  - [ ] `/curator/snapshots` — snapshot list
- [ ] Alumnus detail page (`/directory/[id]`) loads correctly when clicking from directory
- [ ] No unhandled JavaScript errors in browser console on any page
- [ ] Page load time acceptable (<3 s on first load for Overview page)

---

## 5. Database Checklist

- [ ] `alembic_version` table contains revision `<hash of 0009_staging_tables>`
- [ ] All 12 core tables present: STUDY_PROGRAM, INDUSTRY, LOCATION, CAPTURE_SOURCE, COMPANY, COMPANY_ALIAS, ALUMNI, CAREER_RECORD, REFRESH_SNAPSHOT, APP_USER, ROLE, PERMISSION, ROLE_PERMISSION, AUDIT_LOG, IMPORT_BATCH, STAGING_ROW
- [ ] Partial unique index on `CAREER_RECORD.is_current` active (one current role per alumnus)
- [ ] Partial unique index on `ALUMNI.linkedin_url` active (unique when not null)
- [ ] `ALUMNI.validation_status` column uses the `validationstatus` enum type
- [ ] `AUDIT_LOG` table is being written to (verify after any data mutation: import, validate, commit)
- [ ] No orphan `IMPORT_BATCH` rows without a corresponding `AUDIT_LOG` entry

---

## 6. Smoke Tests

Run these in order immediately after the first deployment. All must pass before sharing the URL.

### ST-1: Health
```
GET /health  →  200  {"status":"ok","app_env":"production","database":"connected"}
```

### ST-2: Auth — unauthenticated rejection
```
GET /api/v1/analytics/overview  →  401
GET /api/v1/imports  →  401
```

### ST-3: Login flow
1. Open `https://<app>.vercel.app` in a browser.
2. Enter admin credentials → click Login.
3. Redirected to `/` (Overview page).
4. Page title shows "Overview".

### ST-4: Analytics — overview data
```
GET /api/v1/analytics/overview  (with valid JWT)
→  200  {"total_alumni": N>0, "total_companies": N>0, ...}
```

### ST-5: Filter propagation
In the browser, select a Study Program filter.
- Overview KPIs update.
- Career Outcomes page data updates.
- Directory page rows filter.

### ST-6: Snapshot filter
Select "2025-Q1" in the Snapshot Quarter dropdown.
- Data reflects Q1 cohort only.
Switch to "2025-Q2".
- Data reflects Q2 cohort (higher alumni count due to carry-forward + new graduates).

### ST-7: Import pipeline (curator)
1. Log in as Admin or Data Curator.
2. Create a new snapshot (`2025-Q3` label).
3. Upload `data/synthetic/synthetic_alumni_2025_Q1.csv` as a test (source: Tracer Study).
4. Verify batch summary: 100 rows parsed, 0 errors.
5. **Do not commit** — this is a smoke test only. Delete the snapshot if desired.

### ST-8: Rate limiting
Make 11 rapid POST requests to `/api/v1/imports` (with a valid JWT).
The 11th request returns HTTP 429 with `"Rate limit exceeded"`.

### ST-9: RBAC — Faculty Viewer cannot import
Log in as a Faculty Viewer role user (provision one for testing).
- `POST /api/v1/imports`  →  HTTP 403 "Insufficient permissions."
- `GET /api/v1/analytics/overview`  →  HTTP 200 (analytics:read allowed).

---

## 7. User Acceptance Tests

Run these with an actual curator user account (not the admin) before declaring UAT passed.

### UAT-1: Full quarterly import workflow
1. Curator logs in.
2. Creates snapshot `2025-Q1`.
3. Uploads Q1 synthetic CSV.
4. Reviews batch summary — confirms row counts.
5. Goes to Validation — sees 100 pending alumni.
6. Validates 5 alumni individually, checks program/university fields.
7. Bulk-validates remaining alumni.
8. Commits the snapshot.
9. Goes to Overview → sees validated alumni count.
10. All 6 filter dimensions work on Overview page.

### UAT-2: Second quarter carry-forward
1. Curator creates snapshot `2025-Q2`.
2. Uploads Q2 synthetic CSV (120 rows).
3. Commits Q2 snapshot.
4. Uses Snapshot Quarter filter to compare Q1 vs Q2 totals.
5. Q2 total > Q1 total (20 new graduates added).
6. Director/sector breakdown and geography pages show Q2 data when Q2 selected.

### UAT-3: Alumni directory search
1. Log in as Faculty Viewer.
2. Navigate to `/directory`.
3. Search by name — matching rows appear.
4. Filter by Study Program → rows filter.
5. Click an alumnus row → detail page shows profile + career history.
6. Career history shows snapshot label (`2025-Q1`).

### UAT-4: Company alias management
1. Log in as Data Curator.
2. Navigate to `/curator/companies`.
3. Verify canonical company names are listed with alias counts.
4. Curator can view aliases attached to a company.

### UAT-5: Dedup queue
1. Import a small batch with a deliberate duplicate name (same full_name + program + graduation_year, different linkedin_url).
2. Navigate to `/curator/dedup`.
3. Duplicate pair appears in the queue.
4. Curator can "Keep Separate" or "Merge".

### UAT-6: Role access control
| Action | Admin | Data Curator | Faculty Viewer | Read Only |
|--------|-------|-------------|----------------|-----------|
| View analytics pages | ✅ | ✅ | ✅ | ✅ |
| Access curator import screen | ✅ | ✅ | ❌ (redirected) | ❌ |
| Validate alumni | ✅ | ✅ | ❌ | ❌ |
| Access admin panel | ✅ | ❌ | ❌ | ❌ |

Verify each row matches observed behavior.

---

## 8. Rollback Checklist

If a deployment fails and the previous version must be restored:

### Railway (backend)
- [ ] In Railway dashboard → your service → **Deployments** tab.
- [ ] Find the last successful deployment → click **Rollback**.
- [ ] Railway re-deploys the previous build image without running migrations again.
- [ ] Verify: `GET /health` returns 200 after rollback completes.

> **Migration note:** Alembic does not have a `downgrade` in `railway.toml`. If a bad migration shipped, you must either:
> (a) Deploy a new revision that fixes the migration, or
> (b) Manually run `alembic downgrade -1` from your local machine with `DATABASE_URL` pointing at the live DB, then rollback the code via Railway.

### Vercel (frontend)
- [ ] In Vercel dashboard → your project → **Deployments**.
- [ ] Find the last successful deployment → click the three-dot menu → **Promote to Production**.
- [ ] Verify: the Vercel URL loads the previous version.

### Database
- [ ] If data was corrupted by a bad import: use the `AUDIT_LOG` table to identify affected rows.
- [ ] Rejected alumni (validation_status = rejected) are retained — they can be re-evaluated.
- [ ] If a snapshot was committed incorrectly: there is no automated rollback for committed data. A curator must individually reject the affected alumni records, or delete the snapshot and its career records via the Supabase table editor (admin action, auditable).
- [ ] If Supabase daily backups are enabled: restore from the previous daily backup via Supabase dashboard → Project Settings → Backups → Restore.

### Environment variable rollback
- [ ] If a variable change caused a failure: update the variable in Railway/Vercel to the previous value → auto-redeploy.
- [ ] CORS issue: if `BACKEND_CORS_ORIGINS` was changed incorrectly, the browser will show CORS errors. Fix the value in Railway → redeploy.
