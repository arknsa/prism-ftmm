# PROJECT_CONTEXT.md

> Living project memory. Updated after every artifact.
> **Last updated:** Blocker Resolution Pass — APPROVED (post Artifact #3 review)
> **Artifacts ingested:** [#1 PRD, #2 DB Schema v1, #3 System Architecture v1] + approved blocker resolutions (D-040–D-051)
> **Status:** Architecture NOT yet declared finalized by stakeholder. All technical blockers closed; 2 external legal preconditions remain.

---

## 1. Project Identity

- **Name:** FTMM Alumni Intelligence Dashboard (MVP)
- **Owner / Context:** FTMM — Fakultas Teknologi Maju dan Multidisiplin, Universitas Airlangga.
- **Type:** Centralized alumni analytics & reporting platform.
- **Core purpose:** Replace fragmented alumni data (LinkedIn, tracer studies, spreadsheets, manual records) with a single source of truth for alumni career intelligence.
- **Explicit non-goal:** No AI assistants, chatbots, recommendation systems, RAG, LLM features, confidence scoring, or predictive analytics in MVP.

## 2. Business Problem (Why this exists)

FTMM has no centralized alumni intelligence platform. Consequences today:
- Alumni data fragmented across sources.
- Hard to track graduate outcomes.
- Hard to support accreditation reporting.
- Limited visibility into employer / industry distribution and trends.

## 3. Users

**Primary (the dashboard is built for these):**
- FTMM Faculty Management
- Program Heads
- Career Development Teams
- Alumni Relations Teams

**Secondary (consumers, lower priority):**
- FTMM Students
- FTMM Alumni
- Industry Partners

## 4. Questions the Dashboard Must Answer

1. Where do FTMM alumni work?
2. What positions do alumni hold?
3. Which companies hire FTMM graduates?
4. Which industries employ them?
5. Where are alumni located geographically?
6. How does employment distribution vary by study program?

## 5. Scope Definition of an "FTMM Alumnus" (Business-critical)

A profile is a **valid FTMM alumnus** ONLY IF **both** conditions hold:
- **University = Universitas Airlangga**, AND
- **Program ∈ exactly one of:**
  1. Technology of Data Science
  2. Industrial Engineering
  3. Electrical Engineering
  4. Nanotechnology Engineering
  5. Robotics and Artificial Intelligence Engineering

**Explicitly excluded programs:** Informatics, Information Systems, Statistics, Computer Science, all other UNAIR programs.

**Hard rule:** If a profile does not *explicitly* contain "Universitas Airlangga" AND one approved program, it is **excluded** from MVP. (Strict, deterministic inclusion — no fuzzy/AI inference allowed per scope.)

## 6. Data Sources

**MVP:**
- LinkedIn profiles (primary population source)
- Verified Alumni Records
- Tracer Study Reports

**Future (out of MVP):**
- Alumni Self-Submitted Forms
- IKA Alumni Forms

## 7. Data Collection & Refresh Model

- **Initial population:** LinkedIn-based collection.
- **Refresh:** Quarterly cycle.
- **Data treatment:** LinkedIn data is a **periodic snapshot**, NOT real-time. No real-time synchronization required.
- **Implication captured:** "Snapshot Quarter" is a first-class dimension (appears as a global filter), implying time-versioned data.

## 8. Dashboard Surface (Pages & Widgets)

| Page | Displays |
|------|----------|
| Executive Overview | Total Alumni, Total Companies, Total Industries, Total Locations, Alumni by Program |
| Career Outcomes | Current Roles, Employment Distribution, Seniority Distribution |
| Company Analytics | Top Employers, Company Distribution |
| Industry Analytics | Industry Distribution, Sector Breakdown |
| Geographic Analytics | Country Distribution, City Distribution |
| Alumni Directory | Searchable Alumni Records, Career Information |

**Global filters:** Study Program, Graduation Year, Industry, Company, Country, Snapshot Quarter.

## 9. MVP Scope Boundary

**Included:** Alumni Registry, Company Normalization, Industry Classification, Geographic Mapping, Interactive Dashboards, Quarterly Refresh Workflow.

**Excluded:** Real-time sync, AI verification, confidence scoring, recommendation systems, chatbots, LLM features, advanced predictive analytics.

## 10. Technology Stack (as stated)

- **Frontend:** Next.js, TypeScript, TailwindCSS, Shadcn UI, ECharts
- **Backend:** FastAPI, SQLAlchemy
- **Database:** PostgreSQL (Supabase)
- **Deployment:** Vercel, Railway, Supabase

## 11. Scale & Success

- **Target scale:** 100–1,000 alumni.
- **Success metrics:** centralized DB, consistent company normalization, consistent industry classification, dashboard responsiveness, quarterly refresh capability, faculty-ready reporting.

## 12. Data Architecture (from Artifact #2 — Schema v1)

**Design principles stated:** data quality over automation; validation-first inclusion; historical career preservation; normalized company management; snapshot-based refresh; maintainability; avoid over-engineering.

### Core entities & key fields
| Entity | Key fields / notes |
|--------|--------------------|
| STUDY_PROGRAM | program_id, program_name, degree_level, **is_ftmm_valid** (operationalizes the approved-program rule) |
| ALUMNI | alumni_id, **public_id (UUID)**, full_name, study_program_id (FK), graduation_year, **linkedin_url**, validation_status, created_at, updated_at |
| COMPANY | company_id, canonical_name, industry_id (FK), location_id (FK), country, created_at |
| COMPANY_ALIAS | alias_id, company_id (FK), alias_name, source, created_at — many aliases → 1 canonical company |
| INDUSTRY | industry_id, sector_name, taxonomy_code |
| LOCATION | location_id, country, province, city, region |
| CAREER_RECORD | career_record_id, alumni_id (FK), company_id (FK), role_title, seniority, **is_current**, snapshot_id (FK), captured_on, created_at |
| REFRESH_SNAPSHOT | snapshot_id, quarter_label (e.g. 2025-Q1), refresh_date, notes — enables point-in-time reporting |
| CAPTURE_SOURCE | source_id, source_type, confidence_level (LinkedIn / Verified Faculty Record / Tracer Study / Alumni Form) |
| AUDIT_LOG | audit_id, table_name, record_id, action_type, old_values, new_values, changed_by, changed_at |
| APP_USER / ROLE / PERMISSION / ROLE_PERMISSION | RBAC layer; roles: Admin, Data Curator, Faculty Viewer, Read Only |

### Relationships (declared)
- STUDY_PROGRAM 1→N ALUMNI
- ALUMNI 1→N CAREER_RECORD
- COMPANY 1→N CAREER_RECORD
- INDUSTRY 1→N COMPANY · LOCATION 1→N COMPANY
- REFRESH_SNAPSHOT 1→N CAREER_RECORD
- CAPTURE_SOURCE 1→N CAREER_RECORD *(note: no source FK present on CAREER_RECORD fields — see OPEN_QUESTIONS Q-015 / C-4)*

### Snapshot / history model
- Career facts are **append-style history**: an alumnus has many CAREER_RECORDs; exactly one `is_current=true` at a time (partial unique); old records preserved.
- Each CAREER_RECORD is tagged with `snapshot_id` → point-in-time reporting at **career-record grain**.
- Master entities (ALUMNI, COMPANY, INDUSTRY, LOCATION, STUDY_PROGRAM) are **not** snapshot-versioned.

### Constraints & indexing
- **Unique:** public_id, linkedin_url, canonical company name. **Partial unique:** one active (`is_current`) career record per alumnus.
- **Indexes:** PKs (alumni_id, company_id, career_record_id); filters (graduation_year, study_program_id, company_id, industry_id, snapshot_id, is_current); search (linkedin_url, canonical_company_name).

### Workload & scale assumptions
- Read-heavy; quarterly batch updates; low write concurrency. MVP 100–1,000 alumni; future 5,000+.

### Deployment & non-goals (DB)
- **Supabase PostgreSQL** (managed PG, backups, auth, low ops overhead).
- **Non-goals reaffirmed/extended:** event-driven architecture, microservices, AI-assisted matching, recommendation systems, RAG, chatbots, real-time streaming. **All matching/validation deterministic and curator-controlled.**

---

## 13. System Architecture (from Artifact #3 — v1)

**Architecture principles:** simplicity over complexity; maintainability over optimization; deterministic processing; validation-first workflows; read-heavy optimization; no real-time requirements; no AI-driven decisions.

### Topology
- **Request path:** Users → Next.js (Vercel) → FastAPI (Railway) → Supabase PostgreSQL.
- **Ingest path:** External Sources → **Manual Import Workflow** → FastAPI → Supabase PostgreSQL.
- **Hard rule:** Frontend **never** writes directly to PostgreSQL; all data access flows through FastAPI. DB is **not directly exposed**.
- **AD-001:** FastAPI is the **single business-logic gateway**.

### Component responsibilities
- **Frontend (Next.js/TS/Tailwind/Shadcn/ECharts):** dashboard rendering, filters, search, alumni directory, **auth UI**, **admin tools**.
- **Backend (FastAPI/SQLAlchemy):** auth validation, alumni-validation workflow, company-normalization workflow, industry-classification workflow, data-import processing, dashboard aggregation APIs, audit logging, RBAC.
- **Database (Supabase PG):** alumni/company/industry registries, career history, snapshot history, audit history, user management.

### Authentication flow
User → Login → **Supabase Auth** → **JWT** → FastAPI → **role verification** → authorized API access. Roles: Admin, Data Curator, Faculty Viewer, Read Only.
*(Open: relationship between Supabase Auth users and the schema's APP_USER/ROLE tables — see Q-026 / C-6.)*

### Data ingestion flow (manual)
Dataset (LinkedIn **or** Verified Records **or** Tracer Study) → Import Process → **Validation → Normalization → Deduplication → Snapshot Assignment → DB Storage**.

### Dashboard query flow
User → request → Next.js → FastAPI API → **aggregated query** → PostgreSQL → response → visualization. *(Live SQL aggregation implied; no caching/materialized-view strategy stated — Q-028.)*

### Quarterly refresh workflow
Quarter Start → Data Collection → Validation → Normalization → Snapshot Creation → Dashboard Refresh → Quarter Complete. No real-time updates.

### Deployment (resolves Q-001)
- Frontend → **Vercel** · Backend → **Railway** · Database → **Supabase**.
- Environment variables **managed separately per platform**.

### Security principles
Backend owns business rules · DB not directly exposed · audit logging enabled · RBAC · principle of least privilege.

### Repository
**Monorepo** `ftmm-alumni-platform/`: `frontend/nextjs-app`, `backend/fastapi-app`, `database/{migrations,schema}`, `docs/{prd,architecture,decisions}`, `scripts/{imports,maintenance}`.

### MVP vs Future (architecture)
- **MVP (now):** monolithic FastAPI gateway, manual quarterly batch import, live aggregation, single backend service, Supabase Auth, snapshot model; scale 100–1,000.
- **Future (deferred, explicitly *not justified now*):** Kubernetes, event streaming, Kafka, CQRS, microservices, distributed systems; scale 5,000+.

---

## 14. Ratified Blocker Resolutions (APPROVED — D-040–D-051)

These approved decisions refine Schema v1 / Arch v1 **additively** (no rebuild). See DECISIONS.md §G for full text.

### Identity, validation & dedup
- **Identity:** `public_id` (UUID) is the system identity; `linkedin_url` is **nullable + partial-unique** (D-044).
- **Dedup:** two-tier deterministic — exact LinkedIn URL auto-link, else candidate key (normalized name + program + grad year) → **curator review queue**; no AI (D-045).
- **Validation states:** `pending` / `validated` / `rejected`; only `validated` enters analytics; `rejected` retained (D-047).
- **University:** stored as a `university` attribute on ALUMNI (default UNAIR) + curator-enforced inclusion rule; no UNIVERSITY entity (D-040).

### Provenance & sources
- `source_id` FK added to **CAREER_RECORD** (NOT NULL, D-041) and to **ALUMNI** (primary provenance, D-046).
- `CAPTURE_SOURCE.confidence_level` = **static curator-assigned trust tier** (Verified > Tracer > LinkedIn), never computed (D-049).

### Domain modeling
- **Industry/Sector:** flat INDUSTRY with `industry_name` (granular) + `sector_name` (parent) — serves both Industry Distribution and Sector Breakdown (D-042).
- **Employment semantics:** current career record ⇒ Employed; none ⇒ **Not Reported/Unknown**; dashboard reports "Employed vs Not Reported," **no unemployment rate** (D-048).

### Auth / authorization
- **Supabase Auth = authentication** (JWT with user UUID); **app DB = authorization** (`APP_USER` keyed by Supabase UUID → ROLE/ROLE_PERMISSION); no roles in JWT claims (D-043).

### Compliance posture (technical only; legal pending)
- **LinkedIn:** no in-app scraping; manual offline dataset import; faculty/tracer preferred as system of record (D-050). *Legal sign-off R-001 outstanding.*
- **PII:** RBAC + least privilege, data minimization, retention aligned to snapshots, audit logging (D-051). *Legal basis/consent R-002 outstanding.*

### Net schema delta vs Schema v1 (additive)
`ALUMNI`: +`university`, +`source_id`, `linkedin_url`→nullable+partial-unique, `validation_status`→enum. · `CAREER_RECORD`: +`source_id` (NOT NULL). · `INDUSTRY`: +`industry_name`. · `CAPTURE_SOURCE`: trust-tier semantics. · `APP_USER`: keyed by Supabase UUID. · Cleanups: drop redundant `COMPANY.country`; declare `AUDIT_LOG.changed_by`→APP_USER, `COMPANY_ALIAS.source`→CAPTURE_SOURCE.
