# ENV_AND_SECRETS.md

> Secrets and environment-variable strategy for the FTMM Alumni Intelligence Dashboard.
> **Decision:** D-035 (deploy mapping: Frontend→Vercel · Backend→Railway · DB/Auth→Supabase).
> **Rule:** never commit secret values. Ship `.env.example` files with keys only (no values).

---

## Where secrets live

| Secret | Platform | Why there |
|--------|----------|-----------|
| `DATABASE_URL` | Railway | Backend-only; never browser-exposed |
| `SUPABASE_URL` | Railway + Vercel | Backend uses it for admin client; frontend uses `NEXT_PUBLIC_SUPABASE_URL` (same value) |
| `SUPABASE_SERVICE_ROLE_KEY` | Railway only | Privileged key — must never reach the browser |
| `SUPABASE_JWT_SECRET` | Railway only | Used to verify Supabase-issued JWTs in FastAPI |
| `BACKEND_CORS_ORIGINS` | Railway | Set to the Vercel frontend URL after deploy |
| `APP_ENV` | Railway | `production` in prod; `local` in dev |
| `LOG_LEVEL` | Railway | `INFO` default; `WARNING` in production |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel | Railway backend URL; `NEXT_PUBLIC_*` is browser-safe |
| `NEXT_PUBLIC_SUPABASE_URL` | Vercel | Supabase project URL; public by design |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel | Supabase anon/public key; browser-safe |

---

## Platform-specific setup

### Supabase
Set in **Supabase dashboard** → Project Settings → API:
- Copy `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- Database connection string (pooler): `DATABASE_URL` → Project Settings → Database → Connection String → **Transaction pooler** URI.

### Railway (backend)
Set via **Railway dashboard** → Service → Variables:
```
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://...  (Supabase pooler URI)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key>
SUPABASE_JWT_SECRET=<jwt_secret>
BACKEND_CORS_ORIGINS=https://<app>.vercel.app
```
Railway never exposes these to the browser. The backend is the only consumer.

### Vercel (frontend)
Set via **Vercel dashboard** → Project → Settings → Environment Variables:
```
NEXT_PUBLIC_API_BASE_URL=https://<railway-app>.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```
`NEXT_PUBLIC_*` values are intentionally browser-exposed. They do not contain secrets.

---

## Local development

```bash
# Backend
cd backend/fastapi-app
cp .env.example .env      # then fill in values
# APP_ENV=local is enough to boot; DB calls need DATABASE_URL

# Frontend
cd frontend/nextjs-app
cp .env.example .env.local  # then fill in values
```

Neither `.env` nor `.env.local` is committed — both are covered by the root `.gitignore`
pattern `.env.*` (except `.env.example`, which is explicitly allowed).

---

## Git safety rules

- `.env`, `.env.local`, `.env.*` (except `.env.example`) → excluded by root `.gitignore`.
- Run `git status` before committing to confirm no secret file appears as untracked.
- The CI pipeline (`ci.yml`) does not receive production secrets — tests run against in-memory SQLite mocks, not the live Supabase DB.

---

## Rotation procedure

If a secret is compromised:
1. Rotate in **Supabase dashboard** (generate new key) or **Railway** (update variable).
2. Redeploy the affected service (Railway auto-redeploys on variable change).
3. If `SUPABASE_JWT_SECRET` rotates, all active sessions are immediately invalidated — users must log in again.
4. Update the local `.env` file of any developer who has a copy.

---

## References

- `.env.example` catalogues: [`backend/fastapi-app/.env.example`](../../backend/fastapi-app/.env.example) · [`frontend/nextjs-app/.env.example`](../../frontend/nextjs-app/.env.example)
- Deployment: D-035 · Platform mapping in `README.md` → Tech stack table.
- Railway deployment config: [`backend/fastapi-app/railway.toml`](../../backend/fastapi-app/railway.toml).
