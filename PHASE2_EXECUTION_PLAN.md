# PHASE2_EXECUTION_PLAN.md

> **Phase:** 2 — Authentication & RBAC  
> **Goal:** Supabase authenticates; the app DB authorizes (D-043). A seeded curator/admin can log in, and protected endpoints + routes respect role.  
> **Source of truth:** IMPLEMENTATION_ROADMAP.md (P2.1–P2.6), CLAUDE_CODE_HANDOFF.md §5, DECISIONS.md D-032/D-036/D-043.  
> **Prerequisite:** Phase 1 complete and audited (PHASE1_FINAL_AUDIT.md ✅). Supabase provisioned with `alembic upgrade head` applied and all 5 seed scripts run.

---

## Session Overview

| Session | ID | Roadmap Tasks | Type | Complexity |
|---------|----|--------------|------|-----------|
| [S1](#session-s1--jwt-verification--user-resolver) | S1 | P2.1, P2.2 | Backend | Medium |
| [S2](#session-s2--rbac-guard--me-endpoint) | S2 | P2.3 | Backend | Medium |
| [S3](#session-s3--admin-user-provisioning-flow) | S3 | P2.4 | Backend | Medium |
| [S4](#session-s4--frontend-auth-integration) | S4 | P2.5 | Frontend | Medium |
| [S5](#session-s5--frontend-role-gated-routing) | S5 | P2.6 | Frontend | Medium |

**Execution order:** S1 → S2 → S3 → S4 → S5 (fully sequential; each session unblocks the next).  
**Phase 2 operator prerequisite** (before S1): `SUPABASE_JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `DATABASE_URL` set in Railway environment and local `.env`.

---

## Decision constraints (binding on every session)

- **D-043:** Supabase Auth = authentication only (JWT, `sub` = user UUID). App DB = authorization (`APP_USER` → `ROLE` → `ROLE_PERMISSION`). No roles in JWT claims.
- **D-036:** Least privilege. Backend owns all business rules. DB not directly exposed.
- **D-031:** FastAPI is the single gateway. Frontend never touches DB.
- **D-032:** FastAPI verifies JWT + role before authorizing. Roles: Admin, Data Curator, Faculty Viewer, Read Only.
- **D-002:** No AI/LLM/confidence-scoring anywhere — not relevant to Phase 2 but the rule stands.
- **Golden rule:** if a task seems to need something not in DECISIONS.md D-001–D-051, stop and raise it — do not invent scope.

---

## Session S1 — JWT Verification & User Resolver

### Roadmap tasks covered
- **P2.1** — JWT verification dependency in FastAPI: validate Supabase-issued JWT, extract user UUID (`sub`).
- **P2.2** — `APP_USER` resolver: look up app user by Supabase UUID; load role + permissions (`ROLE_PERMISSION`).

### Objectives
1. Implement a reusable FastAPI dependency that validates an incoming Supabase JWT and extracts the `sub` claim (the Supabase user UUID).
2. Implement a second dependency that uses the extracted UUID to look up the corresponding `APP_USER` row (joined with `ROLE` and `ROLE_PERMISSION`) and returns a typed, in-memory representation of the authenticated user's identity, role, and permission set.
3. Write unit tests for both dependencies covering the happy path and all failure modes (missing header, expired token, invalid signature, unknown UUID, inactive user).

### Deliverables
- `app/dependencies/auth.py` — two FastAPI dependencies: `verify_jwt` and `get_current_user`
- `app/schemas/auth.py` — Pydantic output schemas: `TokenClaims`, `AuthenticatedUser`
- `tests/test_auth_dependencies.py` — unit tests (mock DB + mock JWT library)

### Files expected to be created
```
backend/fastapi-app/app/dependencies/__init__.py
backend/fastapi-app/app/dependencies/auth.py
backend/fastapi-app/app/schemas/__init__.py
backend/fastapi-app/app/schemas/auth.py
backend/fastapi-app/tests/test_auth_dependencies.py
```

### Files expected to be modified
```
backend/fastapi-app/app/config.py        # supabase_jwt_secret already declared; no change needed
backend/fastapi-app/pyproject.toml       # add PyJWT (or python-jose) to dependencies if not present
```

### Dependencies
- **Phase 1 complete:** `APP_USER`, `ROLE`, `PERMISSION`, `ROLE_PERMISSION` tables exist (`app/models/security.py`).
- **Operator:** `SUPABASE_JWT_SECRET` set in environment (value from Supabase project → Settings → API → JWT Secret).
- **S2 not required:** S1 produces the dependency functions; S2 consumes them.

### Implementation notes
- Use **PyJWT** (`pip install PyJWT`) — lightweight, no additional Supabase SDK required at the backend. Supabase JWTs are signed HS256 with the project JWT secret.
- `verify_jwt(authorization: str = Header(...)) -> TokenClaims`: extract `Bearer <token>`, decode with `jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])`, raise `HTTP 401` on any failure. Return `TokenClaims(sub=..., exp=..., role=...)`. The `role` claim in the JWT is ignored for authorization (D-043) but may be logged.
- `get_current_user(claims: TokenClaims = Depends(verify_jwt), session: Session = Depends(get_session)) -> AuthenticatedUser`: query `APP_USER` by `supabase_uuid = claims.sub`; join `ROLE`, `ROLE_PERMISSION`, `PERMISSION`; raise `HTTP 403` if user not found or `is_active = false`; return `AuthenticatedUser(user_id, supabase_uuid, role_name, permissions: frozenset[str])`.
- `AuthenticatedUser.permissions` is a `frozenset[str]` of permission names (e.g. `{"alumni:read", "career:read"}`). This is the object Phase 2 S2 guards will inspect.
- Tests: use `create_autospec(Session, instance=True)` (established Phase 1 pattern) for the DB mock. Use `jwt.encode(...)` with the same secret to create valid test tokens. Test cases: valid token + known active user, valid token + unknown UUID → 403, invalid signature → 401, expired token → 401, inactive user → 403.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_auth_dependencies.py
uv run pytest -v   # all 7 existing tests must still pass
```

### Acceptance criteria
1. `verify_jwt` raises `HTTP 401` for missing, malformed, expired, or wrong-secret tokens.
2. `get_current_user` raises `HTTP 403` for unknown UUID or inactive user.
3. `AuthenticatedUser` carries `role_name` and `permissions` loaded exclusively from the app DB, never from JWT claims (D-043).
4. All new tests pass. All 7 existing tests continue to pass.
5. `ruff`, `black`, `mypy` clean.

### Estimated complexity
**Medium.** JWT decode is library-wrapped; the DB join is straightforward SQLAlchemy. Primary care: test isolation (no real DB, no real Supabase) and typing correctness for mypy strict mode.

---

## Session S2 — RBAC Guard & `/me` Test Endpoint

### Roadmap tasks covered
- **P2.3** — RBAC enforcement utility (route/permission guard) + a protected `/me` test endpoint returning role/permissions.

### Objectives
1. Implement a permission-check utility that any route can use to assert the authenticated user holds a required permission, raising `HTTP 403` if not.
2. Implement the `/me` endpoint (GET) that returns the authenticated user's role and permission list — the canonical integration-test target for Phase 2.
3. Wire the `/me` router into `app/main.py`.
4. Write integration-style tests for `/me` using FastAPI `TestClient` with dependency overrides (no real DB/JWT needed).

### Deliverables
- `app/dependencies/rbac.py` — `require_permission(permission: str)` factory returning a FastAPI dependency
- `app/api/me.py` — `/me` router with `GET /me`
- `app/schemas/me.py` — `MeResponse` Pydantic schema
- `tests/test_me_endpoint.py` — endpoint tests via `TestClient` + dependency overrides

### Files expected to be created
```
backend/fastapi-app/app/dependencies/rbac.py
backend/fastapi-app/app/api/me.py
backend/fastapi-app/app/schemas/me.py
backend/fastapi-app/tests/test_me_endpoint.py
```

### Files expected to be modified
```
backend/fastapi-app/app/main.py              # include me_router
backend/fastapi-app/app/api/__init__.py      # export me_router (if used)
backend/fastapi-app/app/dependencies/__init__.py   # export require_permission
```

### Dependencies
- **S1 complete:** `get_current_user` dependency and `AuthenticatedUser` schema exist.

### Implementation notes
- `require_permission(permission: str)` returns a dependency function: `Depends(get_current_user)` + check `permission in user.permissions` → raise `HTTP 403 {"detail": "Insufficient permissions"}` if not. Usage: `Depends(require_permission("alumni:read"))`.
- `GET /me` response: `{"user_id": int, "supabase_uuid": str, "role": str, "permissions": list[str]}`. Requires only a valid JWT (no specific permission needed — authenticated users can always read their own identity).
- Router prefix: `/me`. Tag: `"auth"`. Include in `main.py` via `app.include_router(me_router)`.
- Tests: override `get_current_user` dependency in `TestClient` to inject a synthetic `AuthenticatedUser`. Test: 200 with correct payload for Admin, 200 for Read Only (different permission set), 401 when dependency raises (simulate missing/bad JWT by overriding to raise `HTTPException(401)`).
- Do **not** add a permission requirement to `/me` itself — identity self-inspection is unconditionally available to any authenticated user.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_me_endpoint.py
uv run pytest -v   # all prior tests still pass
```
Manual (requires live Supabase + a provisioned APP_USER):
```
curl -H "Authorization: Bearer <jwt>" http://localhost:8000/me
# Expected: 200 {"user_id": ..., "role": "Admin", "permissions": [...14 items...]}
```

### Acceptance criteria
1. `GET /me` with a valid JWT returns `200` with `role` and `permissions` from the app DB.
2. `GET /me` with no/invalid JWT returns `401`.
3. `require_permission("some:perm")` returns `403` when the authenticated user lacks that permission.
4. `require_permission("some:perm")` passes through when the user holds the permission.
5. All new and existing tests pass. Linters and mypy clean.

### Estimated complexity
**Medium.** The guard factory pattern is a single function. The endpoint is trivial. Primary effort: clean dependency-override test setup and mypy satisfaction for the generic guard factory.

---

## Session S3 — Admin User-Provisioning Flow

### Roadmap tasks covered
- **P2.4** — Admin user-provisioning flow: create Supabase Auth user + matching `APP_USER` row + role assignment (the only sync point per D-043).

### Objectives
1. Implement an admin-only endpoint (`POST /users`) that provisions a new application user: creates the Supabase Auth user (via Supabase Admin API) and inserts a matching `APP_USER` row with the specified role.
2. Implement an admin-only endpoint (`DELETE /users/{user_id}`) that deactivates an app user (`is_active = false`) and optionally disables the Supabase Auth user — keeping the `APP_USER` row intact for audit integrity.
3. Write tests for both endpoints with mocked Supabase Admin API calls and mocked DB.

### Deliverables
- `app/services/user_provisioning.py` — `provision_user(email, role_name, session) -> AppUser` and `deactivate_user(user_id, session) -> AppUser`
- `app/api/users.py` — `POST /users` and `DELETE /users/{user_id}` (Admin-only)
- `app/schemas/users.py` — `UserCreateRequest`, `UserCreateResponse`, `UserDeactivateResponse`
- `tests/test_user_provisioning.py` — service-layer tests (mocked Supabase)
- `tests/test_users_endpoint.py` — endpoint tests (TestClient + dependency overrides)

### Files expected to be created
```
backend/fastapi-app/app/services/user_provisioning.py
backend/fastapi-app/app/api/users.py
backend/fastapi-app/app/schemas/users.py
backend/fastapi-app/tests/test_user_provisioning.py
backend/fastapi-app/tests/test_users_endpoint.py
```

### Files expected to be modified
```
backend/fastapi-app/app/main.py              # include users_router
backend/fastapi-app/pyproject.toml           # add supabase-py (Admin SDK) if not present
backend/fastapi-app/app/config.py            # supabase_url + supabase_service_role_key already declared; verify sufficient
```

### Dependencies
- **S2 complete:** `require_permission("user:manage")` guard is available.
- **Operator:** `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set (used by Supabase Admin API).

### Implementation notes
- **Supabase Admin SDK:** use `supabase-py` (`pip install supabase`). The service-role key authenticates Admin calls. In `provision_user`: call `supabase.auth.admin.create_user({"email": email, "password": ...})` → get `user.id` (UUID string) → INSERT `APP_USER(supabase_uuid=user.id, role_id=..., email=email, is_active=True)`.
- **Role lookup:** query `ROLE` by `role_name` to get `role_id`. Raise `HTTP 400` if `role_name` is not one of the 4 seeded roles.
- **Deactivation:** set `APP_USER.is_active = False`. Call `supabase.auth.admin.update_user_by_id(supabase_uuid, {"ban_duration": "876600h"})` to disable the Supabase Auth user (effectively permanent ban). Do not delete either row — audit integrity requires the row to remain.
- **Transaction boundary:** the Supabase Admin call happens first; the `APP_USER` INSERT is wrapped in a `session.begin()` block. If the DB write fails after Supabase creation, log a warning with the orphaned UUID so an operator can clean up manually. This is an accepted MVP limitation (no distributed transaction).
- **Password handling:** `POST /users` accepts an initial password in the request body. It is passed directly to Supabase Auth and never stored in the app DB.
- **Audit:** every `APP_USER` insertion and deactivation calls `write_audit_entry()` (P1.14 service, established in Phase 1).
- Both endpoints require `Depends(require_permission("user:manage"))` — Admin-only per ROLE_PERMISSION_MATRIX.md.
- Tests: mock `supabase.auth.admin.create_user` and `update_user_by_id` with `unittest.mock.patch`. Test: successful provision returns correct `APP_USER` fields; unknown role returns 400; deactivation sets `is_active=False`; non-Admin JWT returns 403.

### Validation steps
```powershell
cd backend/fastapi-app
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest -v tests/test_user_provisioning.py tests/test_users_endpoint.py
uv run pytest -v   # all prior tests still pass
```
Manual (requires live Supabase with a provisioned Admin APP_USER):
```
curl -X POST http://localhost:8000/users \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"email":"curator@ftmm.ac.id","password":"...","role_name":"Data Curator"}'
# Expected: 201 {"user_id": ..., "email": "curator@ftmm.ac.id", "role": "Data Curator"}
```

### Acceptance criteria
1. `POST /users` (Admin JWT): creates Supabase Auth user + `APP_USER` row; returns 201.
2. `POST /users` (non-Admin JWT): returns 403.
3. `POST /users` (unknown `role_name`): returns 400.
4. `DELETE /users/{user_id}` (Admin JWT): sets `is_active=False`; Supabase user banned.
5. `APP_USER` row is never deleted (audit integrity preserved).
6. `write_audit_entry()` called for every mutation.
7. All tests pass. Linters and mypy clean.

### Estimated complexity
**Medium.** The logic is straightforward CRUD + one Supabase Admin API call. Primary risk: external Supabase API interaction in tests (use mocks); mypy satisfaction with the Supabase SDK types.

---

## Session S4 — Frontend Auth Integration

### Roadmap tasks covered
- **P2.5** — Supabase Auth client integration in Next.js: login UI, session persistence, token attach to API client (`P0.7`).

### Objectives
1. Integrate `@supabase/ssr` in the Next.js App Router for session persistence using cookies (the SSR-safe approach).
2. Build a minimal login page (`/login`) using Shadcn UI components: email + password form, submit, error display.
3. Extend the existing typed API client (established in Phase 0, `P0.7`) to automatically attach the Supabase `access_token` as a `Bearer` header on every request to FastAPI.
4. Implement logout (clears Supabase session + redirects to `/login`).
5. Verify the login flow calls `GET /me` and retrieves the role/permissions from the backend.

### Deliverables
- `frontend/nextjs-app/lib/supabase/client.ts` — browser-side Supabase client (singleton)
- `frontend/nextjs-app/lib/supabase/server.ts` — server-side Supabase client (SSR/cookies)
- `frontend/nextjs-app/lib/api-client.ts` — updated typed fetch wrapper with auth header injection
- `frontend/nextjs-app/app/(auth)/login/page.tsx` — login page component
- `frontend/nextjs-app/app/(auth)/login/actions.ts` — Server Actions for email/password sign-in and sign-out
- `frontend/nextjs-app/middleware.ts` — Next.js middleware to refresh the Supabase session on each request (SSR cookie rotation)

### Files expected to be created
```
frontend/nextjs-app/lib/supabase/client.ts
frontend/nextjs-app/lib/supabase/server.ts
frontend/nextjs-app/app/(auth)/login/page.tsx
frontend/nextjs-app/app/(auth)/login/actions.ts
frontend/nextjs-app/middleware.ts
```

### Files expected to be modified
```
frontend/nextjs-app/lib/api-client.ts        # inject Authorization header
frontend/nextjs-app/package.json             # add @supabase/ssr @supabase/supabase-js
frontend/nextjs-app/.env.local.example       # add NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### Dependencies
- **S1 complete:** FastAPI's `/me` endpoint validates the JWT from the frontend.
- **S2 complete:** `/me` endpoint is live and returns role/permissions.
- **Operator:** `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in Vercel environment and local `.env.local`.

### Implementation notes
- **Package:** `@supabase/ssr` (not the deprecated `@supabase/auth-helpers-nextjs`). Use the App Router pattern: browser client for client components, server client for Server Components / Server Actions / middleware.
- **Login flow:** Server Action calls `supabase.auth.signInWithPassword({email, password})`. On success, session is persisted in cookies by `@supabase/ssr`. Redirect to `/(dashboard)` (the shell established in Phase 0, `P0.6`).
- **API client:** the existing typed fetch wrapper (from `P0.7`) is updated so that before each request it calls `supabase.auth.getSession()`, extracts `access_token`, and sets `Authorization: Bearer <token>`. If no session, the request proceeds without the header (public endpoints pass through; protected ones return 401 from FastAPI).
- **Middleware:** standard `@supabase/ssr` middleware pattern — refresh session, rotate cookies, forward to next. Match all routes except static assets. This is the recommended SSR-safe approach; no custom cookie logic.
- **Logout:** Server Action calling `supabase.auth.signOut()` → redirect to `/login`.
- **Validation target:** after successful login, the frontend calls `GET /me` on FastAPI (using the injected token); the role and permissions are displayable (even if only logged to console in this session — Phase 5 S5 wires role to the UI).
- **No TypeScript `any` casts.** All Supabase SDK types must flow through.

### Validation steps
```powershell
cd frontend/nextjs-app
pnpm lint
pnpm type-check          # npx tsc --noEmit
pnpm build               # production build must succeed
```
Manual (requires live Supabase, a provisioned Admin APP_USER, and the FastAPI backend running locally):
1. Navigate to `http://localhost:3000/login`.
2. Enter credentials of a provisioned user. Submit.
3. Confirm redirect away from `/login`.
4. Observe browser Network tab: next request to `http://localhost:8000/me` returns `200` with `role` and `permissions`.
5. Logout → redirected back to `/login`. Session cleared.

### Acceptance criteria
1. Login page renders at `/login` with email + password fields and submit button.
2. Successful login redirects away from `/login`.
3. All subsequent API client calls include `Authorization: Bearer <token>`.
4. `GET /me` called post-login returns the authenticated user's role from FastAPI.
5. Logout clears the Supabase session and redirects to `/login`.
6. `pnpm lint`, `pnpm type-check`, and `pnpm build` all pass.

### Estimated complexity
**Medium.** Supabase SSR integration in App Router is well-documented but has SSR-specific pitfalls (cookie rotation, server vs client component split). Primary risk: correctly threading the session through Server Actions and middleware without leaking secrets to the browser.

---

## Session S5 — Frontend Role-Gated Routing

### Roadmap tasks covered
- **P2.6** — Role-gated routing/layout: hide/show nav + guard pages by role; unauthorized state.

### Objectives
1. Create a user-context React context/hook (`useAuth`) that holds the authenticated user's role and permissions (fetched from `GET /me` on mount).
2. Guard the main application layout: redirect unauthenticated users to `/login`; redirect authenticated users away from `/login`.
3. Hide/show navigation items based on the user's role.
4. Implement an `<Unauthorized>` component rendered when an authenticated user tries to access a page their role does not permit.
5. Add a role-gated example: curator-only pages show `<Unauthorized>` to Faculty Viewer and Read Only users.

### Deliverables
- `frontend/nextjs-app/lib/auth-context.tsx` — `AuthProvider`, `useAuth` hook, `AuthenticatedUser` TypeScript type
- `frontend/nextjs-app/components/unauthorized.tsx` — 403-style component with back-link
- `frontend/nextjs-app/app/(dashboard)/layout.tsx` — protected layout: unauthenticated → redirect; authenticated → render with auth context
- `frontend/nextjs-app/app/(dashboard)/admin/page.tsx` — minimal admin-only stub page (demonstrates `user:manage` gate)

### Files expected to be created
```
frontend/nextjs-app/lib/auth-context.tsx
frontend/nextjs-app/components/unauthorized.tsx
frontend/nextjs-app/app/(dashboard)/layout.tsx
frontend/nextjs-app/app/(dashboard)/admin/page.tsx
```

### Files expected to be modified
```
frontend/nextjs-app/app/layout.tsx                  # wrap with AuthProvider (or delegate to dashboard layout)
frontend/nextjs-app/app/(dashboard)/page.tsx         # existing shell: update to render within protected layout
frontend/nextjs-app/components/nav.tsx (or equivalent)   # show/hide items by role
```

### Dependencies
- **S4 complete:** login page, session persistence, and auth-augmented API client exist.

### Implementation notes
- **`AuthProvider`**: a Client Component that calls `GET /me` on mount (using the API client from S4, which already injects the token). Stores `{ user_id, supabase_uuid, role, permissions }` in React context. If `/me` returns 401, calls `supabase.auth.signOut()` and redirects to `/login`. If `/me` returns 200, sets context.
- **`useAuth`**: reads from context; throws if used outside `AuthProvider`.
- **Protected layout** (`app/(dashboard)/layout.tsx`): Server Component checks if the Supabase session exists (using the server Supabase client from S4). If no session → `redirect('/login')`. If session → renders `<AuthProvider>` wrapping `{children}`.
- **Nav visibility**: nav items that require specific permissions are conditionally rendered based on `user.permissions`. Example: "Admin" section in nav visible only when `permissions.includes("user:manage")`. Do not hard-code role names in visibility checks — check permissions (more future-proof per D-036).
- **`<Unauthorized />`**: renders a simple "Access Denied" message with a link back to the dashboard home. Used in pages that need a specific permission the current role lacks.
- **Admin stub page** (`/admin`): a minimal page with `const { user } = useAuth(); if (!user.permissions.includes("user:manage")) return <Unauthorized />;`. Visible in nav only to Admin users.
- **`/login` redirect for authenticated users**: in the login page (`app/(auth)/login/page.tsx`, from S4), add a server-side check: if session already exists → redirect to dashboard.
- Type all `AuthenticatedUser` fields. No `any`.

### Validation steps
```powershell
cd frontend/nextjs-app
pnpm lint
pnpm type-check
pnpm build
```
Manual (using a live Supabase with provisioned users of different roles):

1. **Admin user login:** verify `/admin` page is accessible and "Admin" section appears in nav.
2. **Data Curator login:** verify `/admin` page shows `<Unauthorized />` and "Admin" nav item is hidden.
3. **Read Only login:** verify `/admin` page shows `<Unauthorized />`.
4. **Unauthenticated:** navigate directly to `/dashboard` (or any protected route) → redirected to `/login`.
5. **Authenticated at `/login`:** redirect to dashboard (no flash of login page).

### Acceptance criteria
1. Unauthenticated users are redirected to `/login` from all `/(dashboard)` routes.
2. Authenticated users are redirected away from `/login` to the dashboard.
3. Nav items are shown/hidden according to the authenticated user's permissions.
4. `/admin` page renders `<Unauthorized />` for roles without `user:manage`.
5. `pnpm lint`, `pnpm type-check`, and `pnpm build` all pass.
6. No role names hard-coded in visibility logic — all gating is permission-based.

### Estimated complexity
**Medium.** React context + Server Component session check is a standard Next.js App Router pattern. Primary care: avoiding `useAuth` in Server Components (context is client-only) and ensuring the protected layout does not leak to unauthenticated users via the server-side redirect.

---

## Phase 2 Exit Criterion

Per IMPLEMENTATION_ROADMAP.md:

> *A seeded curator/admin can log in; protected endpoint + route respect role.*

Concrete verification:

1. Admin logs in via `/login` → reaches dashboard.
2. `GET /me` returns `{ role: "Admin", permissions: [...14 items...] }`.
3. `GET /me` called with Data Curator JWT returns `{ role: "Data Curator", permissions: [...11 items...] }`.
4. `GET /me` called with no/invalid JWT returns `401`.
5. `GET /admin` (frontend) with Faculty Viewer session shows `<Unauthorized />`.
6. `POST /users` with Data Curator JWT returns `403`.
7. `POST /users` with Admin JWT + valid payload returns `201` and the new user appears in `APP_USER`.
8. All backend validators pass (`ruff`, `black`, `mypy`, `pytest`).
9. All frontend validators pass (`pnpm lint`, `pnpm type-check`, `pnpm build`).

---

## Complexity Rollup

| Session | Tasks | Backend | Frontend | Complexity |
|---------|-------|---------|---------|-----------|
| S1 | P2.1, P2.2 | JWT dep + user resolver + unit tests | — | Medium |
| S2 | P2.3 | RBAC guard + `/me` endpoint + tests | — | Medium |
| S3 | P2.4 | Provisioning service + endpoints + tests | — | Medium |
| S4 | P2.5 | — | Supabase SSR + login page + API client update | Medium |
| S5 | P2.6 | — | Auth context + gated routing + nav | Medium |

All sessions are Medium complexity. No single session is high-risk in isolation. The highest-risk moment is S3 (external Supabase Admin API call) and S4 (SSR session threading) — mitigated by mocking in tests and the `@supabase/ssr` documented pattern respectively.

---

## New Package Dependencies

| Package | Side | Required by | Notes |
|---------|------|------------|-------|
| `PyJWT` | Backend | S1 | JWT decode; HS256. Prefer over `python-jose` (actively maintained). |
| `supabase` (supabase-py) | Backend | S3 | Admin API calls only (`auth.admin.*`). |
| `@supabase/supabase-js` | Frontend | S4 | Supabase JS client. |
| `@supabase/ssr` | Frontend | S4 | App Router SSR session management. |

---

## Files Summary (all of Phase 2)

### Created
```
backend/fastapi-app/app/dependencies/__init__.py
backend/fastapi-app/app/dependencies/auth.py
backend/fastapi-app/app/dependencies/rbac.py
backend/fastapi-app/app/schemas/__init__.py
backend/fastapi-app/app/schemas/auth.py
backend/fastapi-app/app/schemas/me.py
backend/fastapi-app/app/schemas/users.py
backend/fastapi-app/app/api/me.py
backend/fastapi-app/app/api/users.py
backend/fastapi-app/app/services/user_provisioning.py
backend/fastapi-app/tests/test_auth_dependencies.py
backend/fastapi-app/tests/test_me_endpoint.py
backend/fastapi-app/tests/test_user_provisioning.py
backend/fastapi-app/tests/test_users_endpoint.py
frontend/nextjs-app/lib/supabase/client.ts
frontend/nextjs-app/lib/supabase/server.ts
frontend/nextjs-app/lib/auth-context.tsx
frontend/nextjs-app/app/(auth)/login/page.tsx
frontend/nextjs-app/app/(auth)/login/actions.ts
frontend/nextjs-app/app/(dashboard)/layout.tsx
frontend/nextjs-app/app/(dashboard)/admin/page.tsx
frontend/nextjs-app/components/unauthorized.tsx
frontend/nextjs-app/middleware.ts
```

### Modified
```
backend/fastapi-app/app/main.py                   # include me_router, users_router
backend/fastapi-app/app/api/__init__.py            # exports
backend/fastapi-app/app/dependencies/__init__.py   # exports
backend/fastapi-app/pyproject.toml                 # add PyJWT, supabase
frontend/nextjs-app/lib/api-client.ts              # inject Authorization header
frontend/nextjs-app/app/layout.tsx                 # AuthProvider integration
frontend/nextjs-app/package.json                   # add @supabase/ssr, @supabase/supabase-js
```

### Not touched
```
backend/fastapi-app/app/models/           # Phase 1 models — read-only in Phase 2
backend/fastapi-app/migrations/           # no new migrations in Phase 2
backend/fastapi-app/app/services/audit.py # Phase 1 audit service — consumed but not modified
scripts/imports/                          # Phase 1 seed scripts — not touched
docs/                                     # no documentation changes required in Phase 2
```
