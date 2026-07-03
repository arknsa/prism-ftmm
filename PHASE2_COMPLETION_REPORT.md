# Phase 2 Completion Report — Authentication & RBAC

**Project:** FTMM Alumni Intelligence Dashboard  
**Phase:** 2 — Authentication & Role-Based Access Control  
**Review Date:** 2026-07-01  
**Status:** COMPLETE — Ready for Phase 3

---

## 1. Completed Roadmap Tasks

| Task | Description | Status |
|------|-------------|--------|
| P2.1 | FastAPI JWT verification middleware (`verify_jwt`) | DONE |
| P2.2 | `get_current_user` dependency — JWT → DB user lookup + permissions load | DONE |
| P2.3 | `require_permission` RBAC guard factory + `GET /me` endpoint | DONE |
| P2.4 | `POST /users` and `DELETE /users/{user_id}` provisioning endpoints + service layer | DONE |
| P2.5 | Frontend Supabase Auth integration — browser/server clients, login page, Server Actions, proxy | DONE |
| P2.6 | Frontend role-gated routing — AuthProvider, useAuth, protected layout, permission-based nav, admin stub | DONE |

---

## 2. Acceptance Criteria Status

### P2.1 — JWT Verification
- [x] Rejects missing `Authorization` header → HTTP 401
- [x] Rejects non-Bearer scheme → HTTP 401
- [x] Rejects expired tokens → HTTP 401
- [x] Rejects invalid signature → HTTP 401
- [x] Returns HTTP 503 when `SUPABASE_JWT_SECRET` is not configured
- [x] Extracts `sub`, `exp`, `role` claims into `TokenClaims`

### P2.2 — Authenticated User Lookup
- [x] Resolves `supabase_uuid` → `APP_USER` JOIN `ROLE` JOIN `ROLE_PERMISSION`
- [x] Returns HTTP 403 when user not found in `APP_USER`
- [x] Returns HTTP 403 when `is_active = False`
- [x] Loads permissions as `frozenset[str]` (immutable, hashable)
- [x] `AuthenticatedUser` is frozen Pydantic model

### P2.3 — RBAC Guard + /me
- [x] `require_permission(p)` returns a uniquely-named dependency per permission (DI cache safe)
- [x] Raises HTTP 403 `"Insufficient permissions."` when permission absent
- [x] `GET /me` returns `user_id`, `supabase_uuid`, `role`, `permissions` (sorted list)
- [x] `GET /me` requires valid JWT → authenticated user

### P2.4 — User Provisioning
- [x] `POST /users` requires `user:manage` permission
- [x] `POST /users` creates Supabase Auth user then flushes `APP_USER` (orphan-safe)
- [x] `POST /users` returns HTTP 409 on duplicate email (Supabase)
- [x] `POST /users` returns HTTP 400 on unknown `role_name`
- [x] `DELETE /users/{user_id}` requires `user:manage` permission
- [x] `DELETE /users/{user_id}` bans Supabase user (`ban_duration: "876600h"`) + sets `is_active = False`
- [x] `DELETE /users/{user_id}` returns HTTP 404 for unknown user
- [x] `DELETE /users/{user_id}` returns HTTP 409 if already deactivated
- [x] Audit entries written for both operations

### P2.5 — Frontend Auth Integration
- [x] `createBrowserClient` singleton (guard inside factory, never at module scope)
- [x] `createServerClient` per-request factory with `getAll`/`setAll` cookie adapter
- [x] `setAll` propagates CDN cache-control headers from Supabase
- [x] `proxy.ts` (Next.js 16 convention) refreshes session on every request
- [x] `signIn` Server Action uses `useActionState`-compatible signature
- [x] `signOut` Server Action signs out then redirects to `/login`
- [x] `apiFetch` accepts optional `accessToken` param; `apiFetchWithAuth` dynamically imports browser client (prevents server-side module graph pollution)
- [x] `getMe()` helper typed to `MeResponse`

### P2.6 — Role-Gated Routing
- [x] `AuthProvider` fetches `GET /me` on mount; handles 401 (sign out + redirect) and other errors
- [x] `useAuth()` throws if called outside `<AuthProvider>`
- [x] Dashboard layout Server Component calls `getUser()` (verified) — not `getSession()` (unverified)
- [x] Dashboard layout redirects to `/login` if no authenticated Supabase user
- [x] Login page redirects to `/` if user already authenticated
- [x] `Nav` renders links based on `user.permissions` strings (never role names — D-036)
- [x] Admin page client-side guards on `user:manage` permission
- [x] `<Unauthorized />` component with back-link for access denied states
- [x] All pages opt out of static prerender via `export const dynamic = "force-dynamic"`

---

## 3. Files Created

### Backend
| File | Task |
|------|------|
| `backend/fastapi-app/app/schemas/auth.py` | P2.1/P2.2 — TokenClaims, AuthenticatedUser |
| `backend/fastapi-app/app/dependencies/auth.py` | P2.1/P2.2 — verify_jwt, get_current_user |
| `backend/fastapi-app/app/dependencies/rbac.py` | P2.3 — require_permission factory |
| `backend/fastapi-app/app/api/me.py` | P2.3 — GET /me endpoint |
| `backend/fastapi-app/app/schemas/users.py` | P2.4 — UserCreateRequest/Response, UserDeactivateResponse |
| `backend/fastapi-app/app/services/user_provisioning.py` | P2.4 — provision_user, deactivate_user |
| `backend/fastapi-app/app/api/users.py` | P2.4 — POST /users, DELETE /users/{user_id} |
| `backend/fastapi-app/tests/test_auth_dependencies.py` | P2.1/P2.2 — 24 tests |
| `backend/fastapi-app/tests/test_me_endpoint.py` | P2.3 — 17 tests |
| `backend/fastapi-app/tests/test_user_provisioning.py` | P2.4 — 18 tests |
| `backend/fastapi-app/tests/test_users_endpoint.py` | P2.4 — 19 tests |

### Frontend
| File | Task |
|------|------|
| `frontend/nextjs-app/lib/supabase/client.ts` | P2.5 — browser Supabase client singleton |
| `frontend/nextjs-app/lib/supabase/server.ts` | P2.5 — server Supabase client factory |
| `frontend/nextjs-app/proxy.ts` | P2.5 — Next.js 16 session refresh proxy |
| `frontend/nextjs-app/app/(auth)/login/actions.ts` | P2.5 — signIn/signOut Server Actions |
| `frontend/nextjs-app/app/(auth)/login/login-form.tsx` | P2.6 — LoginForm Client Component |
| `frontend/nextjs-app/lib/auth-context.tsx` | P2.6 — AuthProvider, useAuth hook |
| `frontend/nextjs-app/app/(dashboard)/layout.tsx` | P2.6 — protected dashboard layout |
| `frontend/nextjs-app/app/(dashboard)/page.tsx` | P2.6 — dashboard home shell |
| `frontend/nextjs-app/app/(dashboard)/admin/page.tsx` | P2.6 — admin stub with permission guard |
| `frontend/nextjs-app/components/nav.tsx` | P2.6 — permission-based navigation |
| `frontend/nextjs-app/components/unauthorized.tsx` | P2.6 — access denied component |

---

## 4. Files Modified

| File | Change |
|------|--------|
| `backend/fastapi-app/app/main.py` | Registered me_router, users_router |
| `backend/fastapi-app/pyproject.toml` | Added supabase>=2.0.0, pyjwt>=2.13.0, pydantic[email]>=2.9 |
| `frontend/nextjs-app/lib/api-client.ts` | Added apiFetchWithAuth, getMe, MeResponse, ApiError |
| `frontend/nextjs-app/app/(auth)/login/page.tsx` | Added force-dynamic, auth redirect, LoginForm embed |

---

## 5. Validation Summary

| Validator | Result |
|-----------|--------|
| `pnpm lint` (ESLint, --max-warnings 0) | PASS — 0 warnings, 0 errors |
| `pnpm typecheck` (tsc --noEmit) | PASS — 0 errors |
| `pnpm build` (Next.js production) | PASS — all routes compile; /, /admin, /login all dynamic |
| `ruff check app tests` | PASS — no issues |
| `black --check app tests` | PASS — 34 files unchanged |
| `mypy app` | PASS — no issues found in 27 source files |
| `pytest -v` | PASS — 85/85 tests, 1 deprecation warning (httpx/starlette — upstream, not project code) |

---

## 6. Architecture Compliance

### D-043 Auth/Authz Split
Supabase Auth holds identity only. `APP_USER → ROLE → ROLE_PERMISSION` holds authorization. No roles in JWT claims are used for authorization decisions. FastAPI verifies JWT then queries the DB for permissions. Frontend never makes authorization decisions from JWT data.

### D-036 Permission-Based Nav
`Nav` gates links on `user.permissions` string values (`analytics:read`, `user:manage`). Role names are never used for conditional rendering. This makes nav future-proof against role restructuring.

### D-037 Frontend ↔ Backend Boundary
Frontend never queries the database. All data flows through FastAPI. `apiFetchWithAuth` injects the Supabase JWT as `Authorization: Bearer <token>` for FastAPI to verify.

### D-038 Synthetic Data Only
No real alumni data. All development uses synthetic/fixture data. Legal preconditions R-001/R-002 not yet cleared.

### SSR Security
Dashboard layout calls `supabase.auth.getUser()` (server-side, verified against Supabase Auth server) — not `getSession()` (reads cookies without verification). This prevents session forgery attacks.

### No LLM/AI Features
No AI, ML, RAG, recommender, or predictive features introduced. All logic is deterministic.

---

## 7. Technical Debt

| Item | Severity | Notes |
|------|----------|-------|
| Orphan protection on `provision_user` | LOW | If DB flush fails after Supabase user creation, UUID is logged as WARNING but not automatically cleaned up. Accepted MVP limitation — no distributed transactions. Remediation: periodic orphan-sweep job or saga pattern in future phase. |
| `httpx`/`starlette` deprecation warning in tests | INFO | Upstream library issue (`starlette.testclient` should use `httpx2`). Not project code. Will resolve when `httpx2` adoption spreads. |
| Admin page is a stub | BY DESIGN | `app/(dashboard)/admin/page.tsx` has placeholder content. Full user management UI is Phase 3 scope. |

---

## 8. Remaining Manual Actions (Operator-Dependent)

These tasks are blocked on external account access and cannot be completed by Claude Code:

| Ref | Action | Blocked By |
|-----|--------|------------|
| P0.8 | Provision Supabase project, get URL + anon key + service role key + JWT secret | User's Supabase account |
| P0.9 | Deploy FastAPI to Railway; set env vars: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | User's Railway account |
| P0.10 | Deploy Next.js to Vercel; set env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL` | User's Vercel account |
| P0.11 | Configure CORS: `ALLOWED_ORIGINS` in FastAPI to match Vercel domain | Depends on P0.9/P0.10 |
| — | Run `alembic upgrade head` against real Supabase Postgres | Depends on P0.8/P0.9 |
| — | Run seed scripts to populate `ROLE` and `ROLE_PERMISSION` tables | Depends on migration |
| — | Create initial admin user via `POST /users` (or direct DB insert + Supabase Auth admin) | Depends on seed |

---

## 9. Phase 3 Compatibility Assessment

Phase 2 is forward-compatible with Phase 3 (Alumni Data Ingestion & Curator Workflow):

- **RBAC foundation complete:** `require_permission` factory is ready to gate new endpoints with `alumni:read`, `alumni:write`, `alumni:validate` permissions. No changes to the auth layer needed.
- **API client ready:** `apiFetchWithAuth` can be used by any new Client Component that calls Phase 3 endpoints.
- **`AuthenticatedUser` is frozen/immutable:** Safe to pass through dependency chains.
- **Permission strings (not role names) throughout:** New roles can be added without touching nav or page guards.
- **No LLM/AI scope introduced:** Phase 3 can proceed with deterministic deduplication and curator-controlled validation per DECISIONS.md.
- **Test infrastructure established:** `dependency_overrides` pattern in test files is reusable for Phase 3 endpoint tests.

---

## 10. Readiness for Phase 3

**YES — Phase 2 is complete and Phase 3 can begin.**

All P2.1–P2.6 roadmap tasks are implemented. All validators pass (85 backend tests, 0 lint/typecheck/build errors). The one identified cosmetic issue (`export const dynamic` placement) has been fixed. No open engineering issues remain.
