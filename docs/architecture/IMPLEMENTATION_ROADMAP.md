# IMPLEMENTATION_ROADMAP.md

> Execution roadmap for the FTMM Alumni Intelligence Dashboard MVP.
> **Authoritative inputs:** PROJECT_CONTEXT.md, DECISIONS.md (D-001–D-051), MVP_SCOPE_LOCK.md, ARCHITECTURE_READINESS_REPORT.md.
> **Assumptions:** solo developer · portfolio-grade quality · target scale 100–1,000 alumni · approved scope only · no redesign · no new features.
> **Data note (R-001/R-002):** real alumni PII ingestion is gated on institutional legal sign-off. **All development and the portfolio demo use synthetic/sample data.** The pipeline is built to be production-ready; only the *live data load* waits on legal.

---

## How to read this document

- **Phases** run in order (0 → 7); each is a coherent, demoable increment.
- **Epics** group related work; **Features** group tasks; **Tasks** are the executable units for Claude Code.
- **Task ID:** `P{phase}.{n}`. **Type:** `INFRA` · `DB` · `BE` (backend) · `FE` (frontend) · `DOC`/`TEST`.
- **Complexity:** **S** (≤ half-day) · **M** (~1–2 days) · **L** (multi-day / high-risk).
- **Depends on:** task IDs that must complete first. Tasks with no listed dependency can start when their phase begins.
- Everything maps to an approved decision; no task introduces scope beyond DECISIONS.md.

---

## Phase Map

| Phase | Theme | Primary Epics | Exit criterion (demoable) |
|------|-------|---------------|---------------------------|
| **0** | Foundations & infra bootstrap | A, B(init), M(shell) | Empty app deploys end-to-end; health check green on Railway; frontend shell on Vercel. |
| **1** | Database & reference data | C, J(foundation) | All tables + constraints migrated to Supabase; reference/seed data loaded. |
| **2** | Authentication & RBAC | D | Login works; roles enforced on a protected test endpoint and route. |
| **3** | Import → Validation → Normalization | E, F, G | A synthetic dataset can be imported, validated, and normalized into staging/registry. |
| **4** | Dedup, curator review, snapshots, audit | H, P, I, J | Curator can review/merge/validate; data committed under a snapshot; mutations audited. |
| **5** | Aggregation APIs & global filters | K, L | All six dashboards' data available via filtered aggregation endpoints. |
| **6** | Dashboard pages & alumni directory | N, O, M(finish) | All six pages render real aggregates; directory searchable. |
| **7** | Quarterly refresh E2E, polish, testing, deploy | I(finish), Q, R, B(finish) | Full quarterly cycle demoable; tests pass; production deploy + docs complete. |

---

## Epic Catalogue

| Epic | Name | Phase(s) |
|------|------|----------|
| A | Project Foundation & Tooling | 0 |
| B | Cloud Infrastructure & Deployment Pipeline | 0, 7 |
| C | Database Schema & Reference Data | 1 |
| D | Authentication & RBAC | 2 |
| E | Data Import & Staging | 3 |
| F | Validation & Inclusion Workflow | 3 |
| G | Normalization (company/industry/location/role/seniority) | 3 |
| H | Deduplication & Curator Review | 4 |
| I | Snapshot & Quarterly Refresh | 4, 7 |
| J | Audit Logging | 1, 4 |
| K | Dashboard Aggregation APIs | 5 |
| L | Global Filters | 5 |
| M | Frontend Shell & Design System | 0, 6 |
| N | Dashboard Pages & Visualizations | 6 |
| O | Alumni Directory | 6 |
| P | Curator Admin UI | 4 |
| Q | Portfolio Polish, Docs & Demo Data | 7 |
| R | Testing & Hardening | 7 |

---

# PHASE 0 — Foundations & Infrastructure Bootstrap

**Goal:** a deployable empty skeleton across all three platforms, so every later phase ships continuously.

### Epic A — Project Foundation & Tooling
**Feature A1 — Monorepo scaffold**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P0.1 | Initialize monorepo per approved layout: `frontend/nextjs-app`, `backend/fastapi-app`, `database/{migrations,schema}`, `docs/{prd,architecture,decisions}`, `scripts/{imports,maintenance}`. Add root README. | INFRA | S | — |
| P0.2 | Copy finalized PROJECT_CONTEXT / DECISIONS / MVP_SCOPE_LOCK / READINESS into `docs/`. | DOC | S | P0.1 |
| P0.3 | Tooling config: Python (uv/poetry, ruff, black, mypy), Node (pnpm, eslint, prettier), `.editorconfig`, root `.gitignore`, pre-commit hooks. | INFRA | M | P0.1 |

**Feature A2 — Backend skeleton**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P0.4 | FastAPI app skeleton: settings via env, structured logging, `/health` endpoint, app factory, CORS placeholder. | BE | M | P0.3 |
| P0.5 | SQLAlchemy + Alembic wiring; DB session/engine config; Supabase connection string via env (use Supabase pooler). No models yet. | BE | M | P0.4 |

**Feature A3 — Frontend skeleton (Epic M start)**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P0.6 | Next.js (App Router) + TypeScript + TailwindCSS + Shadcn UI init; base theme tokens; root layout; ECharts dependency installed (not yet used). | FE | M | P0.3 |
| P0.7 | API client layer in frontend (typed fetch wrapper to FastAPI base URL via env). | FE | S | P0.6 |

### Epic B — Cloud Infrastructure (init)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P0.8 | Create Supabase project; capture DB URL + keys; enable Supabase Auth. | INFRA | S | — |
| P0.9 | Create Railway service for backend; configure env vars; deploy P0.4 skeleton; verify `/health`. | INFRA | M | P0.4, P0.8 |
| P0.10 | Create Vercel project for frontend; configure env (backend URL); deploy P0.6 shell. | INFRA | S | P0.6 |
| P0.11 | Configure CORS (Vercel origin ↔ Railway) and a documented per-platform secrets/env strategy (addresses accepted-MVP R-008). | INFRA | M | P0.9, P0.10 |
| P0.12 | Minimal CI (GitHub Actions): lint + typecheck both apps on PR; deploy on main. | INFRA | M | P0.3 |

**Phase 0 exit:** shell frontend on Vercel calls `/health` on Railway successfully; CI green.

---

# PHASE 1 — Database Schema & Reference Data

**Goal:** the full approved schema (Schema v1 + D-040–D-051 deltas) live in Supabase, with seed/reference data and the audit foundation.

### Epic C — Database Schema & Reference Data
**Feature C1 — Core schema models & migrations**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P1.1 | SQLAlchemy models + Alembic migration for **reference tables**: `STUDY_PROGRAM` (incl. `is_ftmm_valid`, `degree_level`), `INDUSTRY` (**`industry_name` + `sector_name` + `taxonomy_code`**, per D-042), `LOCATION` (country/province/city/region), `CAPTURE_SOURCE` (incl. static **trust tier** field per D-049). | DB | M | P0.5 |
| P1.2 | Migration for `COMPANY` (canonical_name unique, industry_id FK, location_id FK; **drop redundant `country`** per Q-021) and `COMPANY_ALIAS` (alias→company, `source`→CAPTURE_SOURCE per Q-023). | DB | M | P1.1 |
| P1.3 | Migration for `ALUMNI` with **D-040/D-044/D-046/D-047 deltas**: `public_id` UUID unique, `university` (default "Universitas Airlangga"), `study_program_id` FK, `graduation_year`, `linkedin_url` **nullable + partial-unique**, `validation_status` **enum{pending,validated,rejected}**, `source_id` FK (primary provenance), timestamps. | DB | M | P1.1 |
| P1.4 | Migration for `CAREER_RECORD` with **D-041 delta**: alumni_id FK, company_id FK, role_title, seniority, `is_current`, `snapshot_id` FK, `source_id` FK **NOT NULL**, captured_on, created_at; **partial unique index** = one `is_current=true` per alumnus (D-020). | DB | M | P1.2, P1.3 |
| P1.5 | Migration for `REFRESH_SNAPSHOT` (quarter_label, refresh_date, notes). | DB | S | P0.5 |
| P1.6 | Migration for **security tables**: `APP_USER` (**keyed by Supabase user UUID** per D-043), `ROLE`, `PERMISSION`, `ROLE_PERMISSION`. | DB | M | P0.5 |
| P1.7 | Migration for `AUDIT_LOG` (table_name, record_id, action_type, old_values JSONB, new_values JSONB, changed_by→APP_USER per Q-023, changed_at). | DB | S | P1.6 |

**Feature C2 — Indexes & constraints**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P1.8 | Apply full **indexing strategy** (D-028): filter indexes (graduation_year, study_program_id, company_id, industry_id, snapshot_id, is_current) + search indexes (linkedin_url, canonical company name). | DB | S | P1.4 |
| P1.9 | Apply **constraints** (D-029): unique public_id, partial-unique linkedin_url, unique canonical_name; verify partial-unique current-career index. | DB | S | P1.4 |

**Feature C3 — Reference & seed data**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P1.10 | Seed `STUDY_PROGRAM` with the **5 approved FTMM programs** (`is_ftmm_valid=true`) and any known non-valid programs flagged false (supports D-003/D-004 validation). | DB | S | P1.3 |
| P1.11 | Seed `CAPTURE_SOURCE` (LinkedIn, Verified Faculty Record, Tracer Study, Alumni Form) with static **trust tiers** (Verified > Tracer > LinkedIn) per D-049. | DB | S | P1.1 |
| P1.12 | Seed `ROLE`/`PERMISSION`/`ROLE_PERMISSION` for the 4 roles (Admin, Data Curator, Faculty Viewer, Read Only) with least-privilege mapping (D-036). | DB | M | P1.6 |
| P1.13 | Seed initial `INDUSTRY` and `LOCATION` reference values (chosen taxonomy standard — resolves build-time Q-006). | DB | M | P1.1 |

### Epic J — Audit Logging (foundation)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P1.14 | Define audit-write service contract (app-level, since all writes pass through FastAPI per D-031). No wiring yet — consumed in Phases 3–4. | BE | S | P1.7 |

**Phase 1 exit:** `alembic upgrade head` builds the entire schema on Supabase; seed scripts populate reference data.

---

# PHASE 2 — Authentication & RBAC

**Goal:** Supabase authenticates; the app DB authorizes (D-043).

### Epic D — Authentication & RBAC
**Feature D1 — Backend auth**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P2.1 | JWT verification dependency in FastAPI: validate Supabase-issued JWT, extract user UUID (`sub`). | BE | M | P0.5, P1.6 |
| P2.2 | `APP_USER` resolver: look up app user by Supabase UUID; load role + permissions (ROLE_PERMISSION). | BE | M | P2.1, P1.12 |
| P2.3 | RBAC enforcement utility (route/permission guard) + a protected `/me` test endpoint returning role/permissions. | BE | M | P2.2 |
| P2.4 | Admin user-provisioning flow: create Supabase Auth user + matching APP_USER row + role assignment (the only sync point per D-043). | BE | M | P2.2 |

**Feature D2 — Frontend auth**
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P2.5 | Supabase Auth client integration in Next.js: login UI, session persistence, token attach to API client (P0.7). | FE | M | P0.7, P2.1 |
| P2.6 | Role-gated routing/layout: hide/show nav + guard pages by role; unauthorized state. | FE | M | P2.5, P2.3 |

**Phase 2 exit:** a seeded curator/admin can log in; protected endpoint + route respect role.

---

# PHASE 3 — Import → Validation → Normalization

**Goal:** turn a raw synthetic dataset into validated, normalized registry candidates. Implements the first four ingestion stages (D-033) up to (but excluding) dedup/snapshot commit.

### Epic E — Data Import & Staging
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P3.1 | Staging tables/models for raw imported rows (per source) with import-batch metadata. | DB | M | P1.4 |
| P3.2 | Import parser service: accept CSV/XLSX per source (LinkedIn / Verified / Tracer), map to a common staging shape, record source + import batch. | BE | L | P3.1, P1.11 |
| P3.3 | Import entry points (resolves Q-027): admin-UI upload endpoint **and** `scripts/imports/` CLI, both writing to staging + audit (J). | BE | M | P3.2, P1.14 |

### Epic F — Validation & Inclusion Workflow
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P3.4 | Program/university matcher (deterministic): map staged program text → canonical `STUDY_PROGRAM`; flag university = UNAIR; no fuzzy/AI (D-040, D-024). Handles program-name variants (Q-005). | BE | L | P3.2, P1.10 |
| P3.5 | Validation-status assignment: set `pending`/`validated`/`rejected` per matcher outcome + curator gate; only valid program+university can become `validated` (D-047). | BE | M | P3.4 |

### Epic G — Normalization
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P3.6 | Company normalization: resolve raw employer text → canonical `COMPANY` via `COMPANY_ALIAS`; create alias/company on first sight (curator-confirmable later); centralized service (D-008/D-017). | BE | L | P3.2, P1.2 |
| P3.7 | Industry classification: attach company → `INDUSTRY` (industry_name/sector_name) at company level (D-018/D-042). | BE | M | P3.6, P1.13 |
| P3.8 | Location normalization: resolve raw location → `LOCATION` (country/province/city/region) (D-019); handle missing/remote. | BE | M | P3.2, P1.13 |
| P3.9 | Role & seniority assignment: store `role_title`; map to a defined seniority ladder deterministically (resolves build-time Q-007/Q-008). | BE | M | P3.2 |

**Phase 3 exit:** importing a synthetic CSV produces staged, validated, normalized candidate records (not yet committed under a snapshot).

---

# PHASE 4 — Deduplication, Curator Review, Snapshots & Audit

**Goal:** complete the ingestion pipeline (dedup → snapshot assignment → storage) and give the curator the tools to drive it. Implements D-045, D-044, D-021, and wires audit (J).

### Epic H — Deduplication & Curator Review (logic)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P4.1 | Tier-1 dedup: exact `linkedin_url` match → auto-link to existing alumnus (D-045). | BE | M | P3.5, P1.3 |
| P4.2 | Tier-2 candidate matcher: deterministic key = normalized(full_name)+study_program_id+graduation_year → produce candidate-duplicate set (D-044/D-045). Name normalization rules (lowercase, trim, strip honorifics). | BE | L | P4.1 |
| P4.3 | Curator review queue model + endpoints: list candidates, confirm-merge, keep-separate; merge operation consolidates onto one `public_id`. | BE | L | P4.2 |

### Epic I — Snapshot & Quarterly Refresh (core)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P4.4 | Snapshot creation service: open/label a `REFRESH_SNAPSHOT` for the quarter (D-021). | BE | S | P1.5 |
| P4.5 | Commit/storage stage: write validated, deduped alumni + `CAREER_RECORD`s tagged with `snapshot_id` + `source_id`; enforce one `is_current` (D-020). | BE | L | P4.3, P4.4 |

### Epic J — Audit Logging (wiring)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P4.6 | Wire audit-write (P1.14) into all mutating operations (import commit, validate/reject, merge, alias edits): capture old/new + changed_by (D-025/D-036). | BE | M | P4.5, P2.2 |

### Epic P — Curator Admin UI
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P4.7 | Import screen: upload dataset, choose source, view batch result/errors. | FE | M | P3.3, P2.6 |
| P4.8 | Validation screen: pending list; validate/reject with reason; shows program/university match result. | FE | M | P3.5, P2.6 |
| P4.9 | Dedup review screen: candidate pairs/groups; confirm-merge / keep-separate. | FE | M | P4.3, P2.6 |
| P4.10 | Company-alias management screen: map aliases → canonical company; correct industry/location. | FE | M | P3.6, P2.6 |
| P4.11 | Snapshot control: open quarter, review summary, finalize commit. | FE | S | P4.5, P2.6 |

**Phase 4 exit:** a curator can run the full pipeline on synthetic data — import → validate → normalize → dedup → commit under `2025-Qx` — with every change audited.

---

# PHASE 5 — Aggregation APIs & Global Filters

**Goal:** filtered, snapshot-aware aggregation endpoints feeding all six pages, using live SQL (D-021; caching deferred to V2 per R-019). Only `validated` alumni are counted (D-047); employment uses "Employed vs Not Reported" (D-048).

### Epic L — Global Filters
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P5.1 | Shared filter contract + query-builder: Study Program, Graduation Year, Industry, Company, Country, **Snapshot Quarter** (D-007). Applied uniformly to all aggregations. | BE | L | P4.5 |
| P5.2 | Filter-options endpoints (distinct programs/years/industries/companies/countries/quarters for populating filter UI). | BE | M | P5.1 |

### Epic K — Dashboard Aggregation APIs
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P5.3 | Executive Overview API: totals (alumni, companies, industries, locations) + alumni-by-program. | BE | M | P5.1 |
| P5.4 | Career Outcomes API: current roles, **Employed vs Not Reported** distribution (D-048), seniority distribution. | BE | M | P5.1 |
| P5.5 | Company Analytics API: top employers, company distribution. | BE | M | P5.1 |
| P5.6 | Industry Analytics API: industry distribution (industry_name) + sector breakdown (sector_name) (D-042). | BE | M | P5.1 |
| P5.7 | Geographic Analytics API: country distribution + city distribution. | BE | M | P5.1 |
| P5.8 | Alumni Directory API: paginated, filterable, searchable list + per-alumnus career detail (Epic O backend). | BE | L | P5.1 |

**Phase 5 exit:** every page's data is retrievable via a documented, filter-aware endpoint returning correct aggregates over the synthetic dataset.

---

# PHASE 6 — Dashboard Pages & Alumni Directory

**Goal:** the six locked pages render real aggregates with ECharts; global filter bar drives all pages; directory is searchable. Finishes Epic M.

### Epic M — Frontend Shell & Design System (finish)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P6.1 | App shell: nav for the six pages, page scaffolding, loading/empty/error states, responsive layout, portfolio-grade theme polish. | FE | M | P2.6 |
| P6.2 | Global filter bar component bound to filter-options endpoints (P5.2); shared filter state across pages incl. Snapshot Quarter switcher. | FE | L | P6.1, P5.2 |
| P6.3 | Reusable ECharts wrappers (bar, pie/donut, map/geo, ranked list) with consistent theming. | FE | M | P6.1 |

### Epic N — Dashboard Pages & Visualizations
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P6.4 | Executive Overview page (KPIs + alumni-by-program chart). | FE | M | P6.2, P6.3, P5.3 |
| P6.5 | Career Outcomes page (roles, Employed-vs-Not-Reported, seniority). | FE | M | P6.2, P6.3, P5.4 |
| P6.6 | Company Analytics page (top employers, distribution). | FE | M | P6.2, P6.3, P5.5 |
| P6.7 | Industry Analytics page (industry distribution + sector breakdown). | FE | M | P6.2, P6.3, P5.6 |
| P6.8 | Geographic Analytics page (country + city; ECharts geo/map). | FE | M | P6.2, P6.3, P5.7 |

### Epic O — Alumni Directory
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P6.9 | Directory page: searchable/filterable table with pagination + career info; respects role visibility. | FE | L | P6.2, P5.8 |
| P6.10 | Alumnus detail view: profile + career history (snapshot-aware). | FE | M | P6.9 |

**Phase 6 exit:** full dashboard is navigable and correct against synthetic data; filters (incl. quarter) work across all pages.

---

# PHASE 7 — Quarterly Refresh E2E, Polish, Testing & Deployment

**Goal:** prove the full quarterly cycle, harden, and ship a portfolio-grade deployment with documentation.

### Epic I — Snapshot & Quarterly Refresh (finish)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P7.1 | End-to-end quarterly refresh orchestration: open snapshot → import → validate → normalize → dedup → commit → dashboards reflect new quarter; carry-forward of unchanged alumni; verify point-in-time correctness across two quarters. | BE | L | P4.5, P6.2 |

### Epic Q — Portfolio Polish, Docs & Demo Data
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P7.2 | **Synthetic data generator** (`scripts/maintenance`): realistic 100–1,000 alumni across the 5 programs, multiple quarters, varied employers/industries/locations — for dev + demo (honors R-001/R-002 by avoiding real PII). | BE | M | P4.5 |
| P7.3 | Seed the live demo with multi-quarter synthetic data; verify every page + filter. | DOC | M | P7.2, P6.10 |
| P7.4 | Documentation set in `docs/`: architecture overview, ER diagram, data-flow, curator runbook (import→commit), env/deploy guide, decisions index. | DOC | M | P6.10 |
| P7.5 | README with screenshots/GIFs, live demo link, feature summary, scope & explicit non-goals (portfolio framing). | DOC | M | P7.3 |

### Epic R — Testing & Hardening
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P7.6 | Backend tests (pytest) focused on the data engine (highest risk): validation matcher, dedup tiers, snapshot commit, aggregation correctness, RBAC guards. | TEST | L | P5.8, P4.6 |
| P7.7 | Frontend tests for critical flows: login/role gating, filter propagation, one chart-render per page (RTL/Playwright, pragmatic for solo). | TEST | M | P6.10 |
| P7.8 | Hardening: input validation on import, error states, least-privilege re-check, health checks, basic rate/size limits on upload; document accepted-MVP risks (R-016/R-017). | BE | M | P7.1 |

### Epic B — Cloud Infrastructure (finish)
| ID | Task | Type | Cx | Depends on |
|----|------|------|----|-----------|
| P7.9 | Production deploy finalization: env/secrets per platform, CORS lock-down, migration-on-deploy for backend, custom domain (optional), CI deploy gates. | INFRA | M | P7.6, P7.7 |

**Phase 7 exit:** two-quarter synthetic cycle demoable end-to-end; tests green; production deploy live with docs and README. **MVP complete.**

---

## Dependency Overview (critical path)

```
P0 (infra+skeletons)
        └─> P1 (schema+seed)
                  └─> P2 (auth/RBAC)
                            └─> P3 (import→validate→normalize)
                                      └─> P4 (dedup→curator→snapshot→audit)
                                                └─> P5 (filters+aggregation APIs)
                                                          └─> P6 (pages+directory)
                                                                    └─> P7 (refresh E2E, tests, polish, deploy)
```

**Notable cross-phase dependencies**
- Audit service is *defined* in P1.14 but *wired* in P4.6 (needs mutations + auth).
- Global filter builder (P5.1) is a hard prerequisite for every aggregation endpoint **and** the frontend filter bar (P6.2).
- Snapshot commit (P4.5) underpins all aggregation correctness and the quarterly E2E (P7.1).
- Frontend pages (P6.4–P6.8) each depend on their matching P5 endpoint + the shared chart/filters infrastructure.

**Parallelizable within a phase (solo dev micro-batching)**
- P3: company (P3.6) / location (P3.8) / role-seniority (P3.9) normalizers are independent after P3.2.
- P5: the six aggregation endpoints (P5.3–P5.8) are independent after P5.1.
- P6: the five chart pages (P6.4–P6.8) are independent after P6.2/P6.3.

---

## Complexity Rollup

| Phase | S | M | L | Phase weight |
|------|:--:|:--:|:--:|:--:|
| 0 | 4 | 7 | 0 | Light–Medium |
| 1 | 5 | 8 | 0 | Medium |
| 2 | 0 | 6 | 0 | Medium |
| 3 | 0 | 4 | 4 | **Heavy** |
| 4 | 2 | 5 | 4 | **Heavy** |
| 5 | 0 | 6 | 2 | Medium–Heavy |
| 6 | 0 | 8 | 2 | Medium–Heavy |
| 7 | 0 | 5 | 3 | Medium–Heavy |

**Heaviest, highest-risk work:** Phases 3–4 (the deterministic ingestion + curation engine) — this is the product's core and where portfolio quality is won or lost. Budget the most time and tests here.

---

## Optimal Build Order (linear, solo dev)

1. **P0.1 → P0.3** scaffold + tooling.
2. **P0.4 → P0.5** backend skeleton + DB wiring; **P0.6 → P0.7** frontend shell + API client.
3. **P0.8 → P0.12** stand up Supabase/Railway/Vercel + CORS + CI (lock the deploy loop early).
4. **P1.1 → P1.9** schema + indexes + constraints; **P1.10 → P1.13** seeds; **P1.14** audit contract.
5. **P2.1 → P2.4** backend auth/RBAC; **P2.5 → P2.6** frontend auth + gating.
6. **P3.1 → P3.3** import/staging; **P3.4 → P3.5** validation; **P3.6 → P3.9** normalization.
7. **P4.1 → P4.5** dedup + snapshot commit; **P4.6** audit wiring; **P4.7 → P4.11** curator UI.
8. **P5.1 → P5.2** filters; **P5.3 → P5.8** aggregation endpoints.
9. **P6.1 → P6.3** shell/filters/charts; **P6.4 → P6.8** pages; **P6.9 → P6.10** directory.
10. **P7.2 → P7.3** synthetic data + demo seed; **P7.1** quarterly E2E; **P7.6 → P7.8** tests + hardening; **P7.4 → P7.5** docs/README; **P7.9** production deploy.

> Rationale: infra-first keeps every increment shippable; schema precedes logic; the ingestion engine (P3–P4) is built and curated before analytics so dashboards always read trustworthy, snapshot-committed data; frontend dashboards come last because they're thin over well-tested APIs.

---

## Guardrails for the execution agent (Claude Code, later)

- Build **strictly** to DECISIONS.md (D-001–D-051). If a task seems to need something not decided, stop and raise it — do **not** invent scope.
- **No** AI/LLM/recommendation/RAG/real-time/streaming/microservices anything (permanent non-goals).
- All matching/validation/dedup remain **deterministic and curator-controlled**.
- **Only `validated` alumni** appear in analytics; employment is **"Employed vs Not Reported"** (never an asserted unemployment rate).
- All writes go through FastAPI and must be audited; the frontend never touches the DB directly.
- Use **synthetic data only** until R-001/R-002 legal preconditions are cleared.
- Target 100–1,000 alumni: prefer clear, correct, live SQL over premature optimization/caching.
