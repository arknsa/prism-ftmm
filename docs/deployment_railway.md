# Backend Deployment — Railway

Runbook for deploying the FastAPI backend (`backend/fastapi-app`) to Railway. This
is deployment configuration only; application behavior is unchanged.

## Build & start

- **Builder:** Nixpacks (`railway.toml`). Nixpacks detects `uv.lock` + `pyproject.toml`
  and provisions `uv`. Set **Root Directory = `backend/fastapi-app`** in Railway so the
  build sees `pyproject.toml`/`railway.toml`.
- **Start command** (`railway.toml`): runs migrations, then serves:
  ```
  uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
  Alembic reads `DATABASE_URL` from the environment (via `migrations/env.py`); `$PORT` is
  injected by Railway.
- **Health check:** `GET /health` (returns `200` with `{status, app_env, database}`;
  `database` is `connected`/`unconfigured`/`error`). `healthcheckTimeout = 120s` covers
  migrate-on-boot + cold start.
- **Restart policy:** `on_failure`, max 3 retries.

## Required environment variables

| Variable | Required | Purpose |
|----------|:--------:|---------|
| `APP_ENV` | **Yes** | Set to `production` — disables `/docs` + `/openapi.json` and enables startup config validation. |
| `DATABASE_URL` | **Yes** | Supabase Postgres pooler URI (session pooler / port 5432). Normalized to `postgresql+psycopg`. |
| `SUPABASE_URL` | **Yes** | `https://<ref>.supabase.co`. Used to fetch the project **JWKS** for ES256 JWT verification (and issuer validation). |
| `BACKEND_CORS_ORIGINS` | **Yes** (for the web frontend) | Comma-separated allowed origins, e.g. `https://your-app.vercel.app`. Empty ⇒ browser requests blocked by CORS. |
| `SUPABASE_SERVICE_ROLE_KEY` | Recommended | Admin API key for user provisioning (`POST /users`, `POST /auth/register`, deactivation). Missing ⇒ those endpoints return 503. |
| `SUPABASE_ANON_KEY` | Optional | Only used by the backend `POST /auth/login` proxy. The web frontend authenticates via Supabase directly and does not need this on the backend. |
| `LOG_LEVEL` | Optional | `DEBUG`/`INFO`/`WARNING`/`ERROR` (default `INFO`; use `WARNING` in prod). Logs are single-line JSON on stdout. |
| `PORT` | Auto | Injected by Railway. |

> `SUPABASE_JWT_SECRET` is **no longer required** — JWT verification moved to ES256/JWKS
> (asymmetric). It can be omitted.

**Startup validation:** in production (`APP_ENV=production`), the app fails fast at boot if
`DATABASE_URL` or `SUPABASE_URL` is missing (`RuntimeError`), and logs warnings when
`BACKEND_CORS_ORIGINS`, `SUPABASE_SERVICE_ROLE_KEY`, or `SUPABASE_ANON_KEY` are unset.

## Deployment procedure

1. **First-time setup (once):** ensure the target database has been migrated and seeded:
   the start command runs `alembic upgrade head` on every deploy (idempotent). Then seed
   RBAC and the first admin (see `scripts/imports/seed_rbac.py` and
   `scripts/imports/bootstrap_admin.py`).
2. **Create the Railway service** from the repo; set **Root Directory** to
   `backend/fastapi-app`.
3. **Set the environment variables** above in the Railway service settings.
4. **Deploy.** On boot: migrations run → uvicorn imports the app → production config is
   validated → server listens on `$PORT`.
5. **Verify:** `GET https://<railway-domain>/health` → `200`, `database: "connected"`.
   `/docs` should be **404/disabled** in production.
6. **Wire the frontend:** set the frontend's `NEXT_PUBLIC_API_BASE_URL` to the Railway URL,
   and ensure `BACKEND_CORS_ORIGINS` includes the Vercel origin.

## Rollback

Re-deploy the previous image/commit from the Railway dashboard. The migration chain is
reversible (`alembic downgrade` is tested), but downgrades are manual and not part of the
start command.
