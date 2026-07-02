# CLAUDE_CODE_HANDOFF.md

> **Single-source briefing for the Claude Code implementation agent.**
> Everything needed to build the FTMM Alumni Intelligence Dashboard MVP **without re-reading the architecture discussions**. If this doc and an older chat disagree, **this doc + DECISIONS.md win**.
> Status: architecture finalized; implementation authorized. Build phase-by-phase per IMPLEMENTATION_ROADMAP.md.

---

## 0. Golden rules (read first, never violate)

1. **Build only approved scope.** Everything traces to DECISIONS.md (D-001–D-051). If a task seems to need something not decided, **stop and ask** — do not invent scope.
2. **Permanent non-goals (never build):** AI assistants, chatbots, RAG, recommendation systems, LLM features, AI/ML matching, AI verification, confidence *scoring*, predictive analytics, real-time sync/streaming, microservices, event-driven, Kafka, CQRS, Kubernetes, distributed systems.
3. **All matching/validation/dedup is deterministic and curator-controlled.** No fuzzy/AI matching anywhere.
4. **Only `validated` alumni appear in analytics.** Employment is reported as **"Employed vs Not Reported"** — never assert an unemployment rate.
5. **Frontend never touches the database.** All data access goes through FastAPI (the single business-logic gateway). Every write is audited.
6. **Use synthetic data only** until legal preconditions R-001/R-002 are cleared. The pipeline is production-ready; the live PII load is gated externally.
7. **Quality bar:** portfolio-grade. Clear, correct, documented, tested where it matters. Scale target is **100–1,000 alumni** — favor correctness and clarity over premature optimization/caching.

---

## 1. What this project is

A centralized analytics dashboard for FTMM (Fakultas Teknologi Maju dan Multidisiplin), Universitas Airlangga, that consolidates fragmented alumni career data into one source of truth and answers: where alumni work, what roles/seniority they hold, which companies/industries employ them, where they're located, and how this varies by study program. **Analytics & reporting only.**

**Primary users:** Faculty Management, Program Heads, Career Development, Alumni Relations. **Secondary:** Students, Alumni, Industry Partners.

---

## 2. Tech stack (fixed)

| Layer | Choice |
|------|--------|
| Frontend | Next.js (App Router) + TypeScript + TailwindCSS + Shadcn UI + **ECharts** |
| Backend | FastAPI + SQLAlchemy (+ Alembic migrations) |
| Database | PostgreSQL on **Supabase** |
| Auth | **Supabase Auth** (authentication) + **app-DB RBAC** (authorization) |
| Deploy | Frontend → **Vercel** · Backend → **Railway** · DB/Auth → **Supabase** |
| Repo | **Monorepo** |

**Monorepo layout:** `frontend/nextjs-app`, `backend/fastapi-app`, `database/{migrations,schema}`, `docs/{prd,architecture,decisions}`, `scripts/{imports,maintenance}`.

---

## 3. Data model (finalized = Schema v1 + approved deltas D-040–D-051)

**Reference / taxonomy**
- `STUDY_PROGRAM` — program_id, program_name, degree_level, **is_ftmm_valid** (the 5 approved programs are true).
- `INDUSTRY` — industry_id, **industry_name** (granular), **sector_name** (parent group), taxonomy_code.
- `LOCATION` — location_id, country, province, city, region.
- `CAPTURE_SOURCE` — source_id, source_type, **trust tier** (static, curator-assigned: Verified > Tracer > LinkedIn; never computed). *(field was `confidence_level`; reinterpreted, optional rename `trust_level`.)*

**Core**
- `ALUMNI` — alumni_id, **public_id (UUID, unique = system identity)**, full_name, **university** (default "Universitas Airlangga"), study_program_id→STUDY_PROGRAM, graduation_year, **linkedin_url (nullable, partial-unique)**, **validation_status (enum: pending | validated | rejected)**, **source_id→CAPTURE_SOURCE** (primary provenance), created_at, updated_at.
- `COMPANY` — company_id, canonical_name (unique), industry_id→INDUSTRY, location_id→LOCATION, created_at. *(redundant `country` removed.)*
- `COMPANY_ALIAS` — alias_id, company_id→COMPANY, alias_name, source→CAPTURE_SOURCE, created_at. (Many aliases → one canonical company.)
- `CAREER_RECORD` — career_record_id, alumni_id→ALUMNI, company_id→COMPANY, role_title, seniority, **is_current** (exactly one true per alumnus — partial-unique), snapshot_id→REFRESH_SNAPSHOT, **source_id→CAPTURE_SOURCE (NOT NULL)**, captured_on, created_at.
- `REFRESH_SNAPSHOT` — snapshot_id, quarter_label (e.g. `2025-Q1`), refresh_date, notes.

**Security & audit**
- `APP_USER` — **keyed by the Supabase user UUID**, holds app role. `ROLE`, `PERMISSION`, `ROLE_PERMISSION` — RBAC. Roles: **Admin, Data Curator, Faculty Viewer, Read Only**.
- `AUDIT_LOG` — audit_id, table_name, record_id, action_type, old_values (JSONB), new_values (JSONB), **changed_by→APP_USER**, changed_at.

**Indexing:** PKs + filter indexes (graduation_year, study_program_id, company_id, industry_id, snapshot_id, is_current) + search indexes (linkedin_url, canonical company name).
**Constraints:** unique public_id; partial-unique linkedin_url (when present); unique canonical_name; partial-unique one current career record per alumnus.

---

## 4. Core business rules

- **Alumnus validity (strict, deterministic):** university = Universitas Airlangga **AND** program ∈ {Technology of Data Science, Industrial Engineering, Electrical Engineering, Nanotechnology Engineering, Robotics and Artificial Intelligence Engineering}. Anything not explicitly matching is excluded. University is enforced in the curator validation workflow + stored as an attribute (no university entity).
- **Validation states:** `pending` (imported, awaiting curator), `validated` (in analytics), `rejected` (excluded, retained for audit/anti-churn). **Only `validated` counts.**
- **Identity & dedup:** identity = `public_id` UUID. Dedup is two-tier and deterministic: (1) exact `linkedin_url` match → auto-link; (2) candidate key = normalized(full_name)+study_program_id+graduation_year → **curator review queue** (confirm-merge / keep-separate). Normalize = lowercase, trim, collapse whitespace, strip honorifics. No AI.
- **Snapshots:** quarterly. `REFRESH_SNAPSHOT` + `career_record.snapshot_id` give point-in-time reporting **at career-record grain**. Master entities (company/industry/program) are **not** versioned (accepted MVP limitation).
- **Employment semantics:** alumnus with a current career record ⇒ **Employed**; none ⇒ **Not Reported/Unknown**. Report "Employed vs Not Reported." No unemployment rate.
- **Source trust tier:** static, set per `CAPTURE_SOURCE`; used only as a human tie-breaker in conflict resolution, never to auto-decide inclusion.
- **Industry attribution:** industry is attached at the **company** level; an alumnus's industry derives from their company.

---

## 5. Auth & RBAC model (D-043)

- **Supabase Auth = authentication only:** login + issues JWT carrying the user UUID (`sub`).
- **App DB = authorization:** FastAPI verifies the JWT, looks up `APP_USER` by Supabase UUID, loads role via `ROLE`/`ROLE_PERMISSION`, enforces RBAC per request. **No roles in JWT claims.**
- **User provisioning** (the only sync point): create a Supabase Auth user **and** a matching `APP_USER` row + role assignment.
- Principle of least privilege; DB never exposed directly; all business rules in the backend.

---

## 6. Workflows

**Manual import pipeline (per dataset):** Import → Validation → Normalization → **Deduplication** → Snapshot Assignment → DB Storage. Sources: LinkedIn dataset, Verified Faculty Records, Tracer Study. Import entry points: admin-UI upload **and** `scripts/imports/` CLI; both write to staging + audit. **No in-app scraping.**

**Quarterly refresh:** open snapshot → collect → validate → normalize → dedup → commit under the quarter → dashboards reflect it. No real-time.

**Curator tools (frontend, Phase 4):** import screen, validation (pending) screen, dedup review queue, company-alias management, snapshot finalize.

---

## 7. The six dashboard pages + filters (locked)

| Page | Content |
|------|---------|
| Executive Overview | Totals: alumni, companies, industries, locations; alumni by program. |
| Career Outcomes | Current roles; **Employed vs Not Reported**; seniority distribution. |
| Company Analytics | Top employers; company distribution. |
| Industry Analytics | Industry distribution (industry_name); sector breakdown (sector_name). |
| Geographic Analytics | Country distribution; city distribution. |
| Alumni Directory | Searchable, filterable alumni records + career info. |

**Global filters (all pages):** Study Program, Graduation Year, Industry, Company, Country, **Snapshot Quarter**.
**Aggregation:** live SQL via FastAPI endpoints (caching is V2). Charts via ECharts.

---

## 8. Build order (phases) — see IMPLEMENTATION_ROADMAP.md for task detail

0. Foundations & infra bootstrap → 1. Database & reference data → 2. Auth & RBAC → 3. Import→Validate→Normalize → 4. Dedup, curator UI, snapshots, audit → 5. Aggregation APIs & filters → 6. Dashboard pages & directory → 7. Quarterly refresh E2E, polish, tests, deploy.

- **Heaviest/highest-risk:** Phases 3–4 (the deterministic ingestion + curation engine). Concentrate tests here.
- **Linchpin:** the shared filter builder (roadmap P5.1) — prerequisite for every aggregation endpoint and the frontend filter bar.
- Audit service is defined in Phase 1, wired in Phase 4.
- **Start with Phase 0** using PHASE0_EXECUTION_PLAN.md.

---

## 9. Environment variables (catalogue)

Backend: `DATABASE_URL` (Supabase pooler), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `BACKEND_CORS_ORIGINS`, `APP_ENV`.
Frontend: `NEXT_PUBLIC_API_BASE_URL` (Railway URL), `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_ANON_KEY`.
Secrets are set **per platform** (Railway / Vercel / Supabase); never commit values; ship `.env.example` with keys only.

---

## 10. Decision quick-index (D-001–D-051)

- **Scope/non-goals:** D-001 (analytics only), D-002 (no AI/LLM), D-003/D-004 (strict 5-program validity), D-005 (3 MVP sources), D-030/D-038 (no microservices/streaming/K8s/CQRS).
- **Data model:** D-006/D-021 (quarterly snapshots, career-record grain), D-017 (company+alias normalization), D-018/D-042 (industry at company level; flat INDUSTRY with industry_name+sector_name), D-019 (LOCATION), D-020 (career history, one current), D-022/D-049 (provenance; static trust tier), D-023/D-044 (UUID identity; linkedin_url nullable+partial-unique), D-024/D-047 (curator validation; status enum), D-040 (university attribute), D-041/D-046 (source_id FKs on CAREER_RECORD/ALUMNI), D-045 (deterministic two-tier dedup), D-048 (Employed vs Not Reported).
- **Architecture:** D-011–D-014 (stack), D-031 (single FastAPI gateway), D-032/D-043 (Supabase authn + app-DB authz), D-033/D-034 (manual import + quarterly refresh), D-035 (deploy mapping), D-036 (security), D-037 (monorepo), D-039 (principles).
- **Compliance posture (legal pending):** D-050 (no in-app scraping), D-051 (PII safeguards).

---

## 11. Known accepted limitations & deferred-to-V2 (do not "fix" in MVP)

- Strict match may undercount alumni (accepted; curators monitor).
- Master-entity classifications not snapshot-versioned (point-in-time at career grain only).
- No caching/materialized views (live SQL is fine at this scale).
- Single FastAPI gateway SPOF + Supabase vendor concentration (accepted MVP).
- No alumni-growth/trend page (V2).
- Real PII ingestion blocked on R-001 (LinkedIn legal) and R-002 (UU PDP consent/basis) — **use synthetic data**.

---

## 12. Artifacts to prepare before later phases (not blockers for Phase 0)

- **Before Phase 1:** consolidated ER diagram; concrete role→permission matrix.
- **Before Phase 3:** industry taxonomy standard; seniority ladder; program-name variant→canonical mapping rules.
- **Before Phases 3/5:** API contract / OpenAPI outline for curation + aggregation endpoints.
- **Before Phases 4/6:** UI wireframes + theme tokens (colors/typography).
- **Anytime from Phase 3:** synthetic data spec/generator.

---

## 13. Definition of done (per task, general)

A task is done when: it implements exactly its roadmap scope; matches the relevant decisions; passes lint + typecheck; has tests where it touches the data engine, validation, dedup, aggregation, or RBAC; writes to AUDIT_LOG if it mutates data; and is reflected in `docs/` if it changes a contract. Deploys must stay green (CI). Never broaden scope to "be helpful" — raise it instead.
