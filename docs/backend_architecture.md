# Backend Architecture — PRISM (FTMM Alumni Intelligence Dashboard)

**Status:** Baseline (Phases 1–3 frozen). This document describes the backend exactly as it stands.
**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (sync) · psycopg 3 · Alembic · Pydantic v2 · Supabase (Auth + Postgres) · Railway (deploy) · `uv` (packaging).

---

## 1. Project architecture

The backend is a single **business-logic gateway** (D-031): the frontend never touches the database directly — all reads/writes flow through this FastAPI app, which owns authentication, authorization, validation, and auditing.

Layered, dependencies point inward:

```
┌────────────────────────────────────────────────────────────┐
│  API layer  (app/api/*)          thin HTTP controllers      │
│    - routing, status codes, request/response schemas        │
│    - declares auth/permission dependencies                  │
└───────────────┬────────────────────────────────────────────┘
                │ calls
┌───────────────▼────────────────────────────────────────────┐
│  Service layer  (app/services/*)   business logic           │
│    - takes an injected Session; caller owns the commit       │
│    - no HTTP awareness beyond raising HTTPException          │
└───────────────┬────────────────────────────────────────────┘
                │ uses
┌───────────────▼────────────────────────────────────────────┐
│  Model layer  (app/models/*)    SQLAlchemy 2.0 ORM          │
│    - declarative mapped classes on Base.metadata            │
└───────────────┬────────────────────────────────────────────┘
                │ persisted via
┌───────────────▼────────────────────────────────────────────┐
│  DB access  (app/db.py)   engine + sessionmaker (lazy)      │
│    → Supabase Postgres (pooler)                             │
└────────────────────────────────────────────────────────────┘

Cross-cutting: app/config.py (settings), app/logging.py (JSON logs),
app/rate_limiting.py (IP limiter), app/dependencies/* (auth, rbac).
```

There is **no separate repository layer**: services use the SQLAlchemy `Session` (Unit of Work) directly. This is a deliberate simplification — the ORM/session *is* the data-access abstraction. Query construction lives in services (and a few read endpoints), always parameterized.

---

## 2. Folder structure

```
backend/fastapi-app/
├── app/
│   ├── main.py                 # create_app() factory + module-level app
│   ├── config.py               # Settings (pydantic-settings), get_settings() cached
│   ├── db.py                   # Base, lazy engine, sessionmaker, get_session, ping
│   ├── logging.py              # JSON formatter, configure_logging
│   ├── rate_limiting.py        # in-memory sliding-window IP limiter (import uploads)
│   ├── api/                    # routers (one module per domain)
│   │   ├── health.py           # GET /health
│   │   ├── auth.py             # /auth/{login,register,me}
│   │   ├── me.py               # GET /me
│   │   ├── users.py            # POST /users, DELETE /users/{id}
│   │   ├── imports.py          # /api/v1/imports*
│   │   ├── dedup.py            # /api/v1/dedup/*        (Phase 4)
│   │   ├── snapshots.py        # /api/v1/snapshots*     (Phase 4)
│   │   ├── commit.py           # /api/v1/commit + /api/v1/alumni* (Phase 4)
│   │   ├── company.py          # /api/v1/companies*, /api/v1/aliases* (Phase 4)
│   │   └── analytics.py        # /api/v1/analytics/*    (Phase 5)
│   ├── dependencies/
│   │   ├── auth.py             # verify_jwt, get_current_user
│   │   └── rbac.py             # require_permission(perm) factory
│   ├── schemas/                # Pydantic v2 request/response models per domain
│   ├── services/               # business logic (import_parser, authentication,
│   │                           #   user_provisioning, audit, dedup*, commit*,
│   │                           #   snapshot, analytics*, normalization services)
│   └── models/                 # SQLAlchemy models (17 tables) + __init__ registry
├── migrations/                 # Alembic env + versions/0001..0010
├── tests/                      # pytest (683 tests, DB fully mocked)
├── alembic.ini
├── pyproject.toml / uv.lock
├── railway.toml
└── .env.example
```

---

## 3. Startup sequence

1. **Import time** — `app.main` executes `app = create_app()` ([main.py](../backend/fastapi-app/app/main.py)).
2. `get_settings()` reads env / `.env` once (cached via `lru_cache`).
3. `configure_logging(level)` installs the JSON formatter on the root logger and re-points uvicorn loggers to it.
4. Docs are gated: `docs_url`/`openapi_url` are `None` when `APP_ENV=production`.
5. `FastAPI(...)` is constructed; **CORS middleware** added from `BACKEND_CORS_ORIGINS`.
6. **Ten routers** are registered (see §7).
7. An `app_init` log line is emitted.
8. **The database engine is NOT created here.** `app/models` is imported (registering all classes on `Base.metadata`) but the SQLAlchemy engine is built lazily on first DB use (`get_engine()`), so the app can boot even before the DB is reachable — a health check can respond immediately.
9. **Runtime** — Railway runs `uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT` ([railway.toml](../backend/fastapi-app/railway.toml)).

---

## 4. Request lifecycle

```
HTTP request
  → CORS middleware
  → routing (match path + method)
  → dependency resolution (in declaration order):
        get_session()          → yields a Session (per request)
        verify_jwt(Authorization) → TokenClaims        [auth’d routes]
        get_current_user(claims, session) → AuthenticatedUser
        require_permission(P)(user) → 403 if P absent   [guarded routes]
        import_rate_limit(request) → 429 if over limit  [upload only]
  → route handler executes (calls services)
  → return value validated/serialized via response_model
  → get_session finally-block closes the Session
     (any uncommitted work is rolled back on close)
HTTP response
```

Errors are surfaced as `HTTPException` (mapped to the right status) or, for unexpected failures in the import path, logged with a stack trace and re-raised as 500 after rollback.

---

## 5. Dependency injection flow

FastAPI resolves a small, composable dependency graph:

```
get_session ─────────────────────────────┐
                                          ▼
Authorization header ─► verify_jwt ─► get_current_user ─► AuthenticatedUser
                          (TokenClaims)       ▲
                                              │
require_permission("x") ──────────────────────┘  (wraps get_current_user,
                                                   asserts "x" ∈ permissions)

_get_supabase_client()   built per-request in auth.py / users.py (service-role)
import_rate_limit(request)  IP sliding-window guard (upload only)
```

- **`get_session`** ([db.py](../backend/fastapi-app/app/db.py)) — yields a request-scoped `Session`, closed in `finally`.
- **`verify_jwt`** ([dependencies/auth.py](../backend/fastapi-app/app/dependencies/auth.py)) — validates the Supabase JWT, returns `TokenClaims(sub, exp, role)`.
- **`get_current_user`** — resolves `AuthenticatedUser` from the DB (identity + role + permissions).
- **`require_permission(perm)`** ([dependencies/rbac.py](../backend/fastapi-app/app/dependencies/rbac.py)) — factory returning a guard that reuses `get_current_user` and raises 403 if the permission is absent. Each guard gets a unique `__name__` for correct dependency-cache behavior.

Tests override these via `app.dependency_overrides` (no real DB/Supabase).

---

## 6. Authentication flow

Supabase Auth is the **authentication** provider (identity only). D-043.

```
POST /auth/login {email, password}
  → authenticate_user(): supabase.auth.sign_in_with_password(...)
       ├─ invalid creds → 401
       ├─ verify APP_USER exists + is_active → else 403
       └─ returns Supabase session tokens (access + refresh) + app identity
Client stores access_token, sends: Authorization: Bearer <token>
  → verify_jwt():
       ├─ scheme must be "Bearer"
       ├─ jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], verify_aud=False)
       ├─ ExpiredSignatureError → 401 ("Token has expired")
       ├─ InvalidTokenError     → 401 ("Invalid token")
       ├─ require sub:str, exp:int → else 401
       └─ TokenClaims(sub=<supabase_uuid>, exp, role=<logging only>)
```

- Algorithm is **pinned to HS256** (no alg-confusion). The JWT `role` claim is captured for logging **only**.
- `SUPABASE_JWT_SECRET` unset → 503 (auth unavailable).

---

## 7. Authorization flow (D-043)

Authorization is decided **exclusively from the app database**, never from JWT claims.

```
get_current_user(claims):
  SELECT app_user JOIN role WHERE app_user.supabase_uuid = claims.sub
    ├─ not found        → 403 ("User not found in application registry")
    ├─ is_active = false → 403 ("User account is inactive")
    └─ SELECT permission_name
          JOIN role_permission ON permission.permission_id = role_permission.permission_id
          WHERE role_permission.role_id = role.role_id
  → AuthenticatedUser(user_id, supabase_uuid, role_name, permissions: frozenset)

require_permission("alumni:read"):
  → if "alumni:read" not in user.permissions: 403 ("Insufficient permissions")
```

**Roles (D-026):** Admin, Data Curator, Faculty Viewer, Read Only.
**Permission names (14):** `alumni:read`, `alumni:write`, `alumni:validate`, `alumni:delete`, `career:read`, `career:write`, `company:read`, `company:write`, `import:run`, `dedup:review`, `snapshot:manage`, `audit:read`, `user:manage`, `analytics:read`.
The role→permission mapping lives in the DB (`role_permission`), seeded per `ROLE_PERMISSION_MATRIX.md`.

---

## 8. Router / service / model architecture

| Concern | Owns | Does NOT |
|---------|------|----------|
| **Router** (`api/`) | HTTP shape: path, method, status codes, request/response schemas, auth/permission dependencies, commit boundary | business rules |
| **Service** (`services/`) | business logic, validation, DB reads/writes on the injected session, `HTTPException` on domain errors | open/close sessions, commit (caller owns it) |
| **Model** (`models/`) | table mapping, column types, relationships | queries |

Contract: **services add to / query the session but do not commit**; the router commits (or the request ends and uncommitted work rolls back). This lets a mutation + its audit entry commit atomically ([services/audit.py](../backend/fastapi-app/app/services/audit.py)).

---

## 9. Database access layer

- **Base:** `class Base(DeclarativeBase)` ([db.py](../backend/fastapi-app/app/db.py)). No `naming_convention` (see known warning M1).
- **Engine:** created lazily by `get_engine()` with `pool_pre_ping=True` (guards stale Supabase-pooler connections) and `future=True`. URL normalized to the `postgresql+psycopg` (psycopg 3) driver via `_normalize_url()`.
- **Sessions:** `sessionmaker(autoflush=False, expire_on_commit=False)`; one `Session` per request via the `get_session` generator dependency.
- **Connectivity check:** `ping()` runs `SELECT 1`, returns `False` (never raises) when unconfigured/unreachable — used by `/health`.
- **Migrations:** Alembic; `migrations/env.py` injects `DATABASE_URL` from settings and uses `target_metadata = Base.metadata` for autogenerate.

---

## 10. Transaction flow

```
Request
  └─ get_session yields Session S            (no transaction opened yet)
       └─ handler / services do S.add / S.execute / S.query
       └─ handler calls S.commit()           ← success path
            or on error: S.rollback()         ← failure path
  └─ get_session finally: S.close()          (uncommitted ⇒ rolled back)
```

**Import example (atomic, EP-1):**
```
parse_import(): S.add(batch); S.flush()  → batch_id
                S.execute(insert(StagingRow), [rows...])   # single bulk insert
write_audit_entry(S, ...)                # S.add(AuditLog)
S.commit()                               # batch + rows + audit commit together
except (ValueError | UnicodeDecodeError | csv.Error): S.rollback() → 400
except Exception: S.rollback(); log stack; re-raise → 500
```

No orphan batch or audit row is ever committed on failure (verified by `test_import_atomicity.py`).

---

## Appendix — key design decisions referenced

- **D-025** audit every mutation · **D-026/D-036** RBAC least-privilege · **D-031** single gateway · **D-033** manual import workflow · **D-043** Supabase = authn, app DB = authz · **D-044** UUID public id + partial-unique linkedin · **D-020/D-029** one current career record per alumnus.
