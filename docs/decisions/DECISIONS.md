# DECISIONS.md

> Confirmed decisions extracted from artifacts. Each is tagged by source.
> **Last updated:** Blocker Resolution Pass — APPROVED (post Artifact #3 review)
> Decision IDs are stable; new artifacts append or supersede (superseded ones are struck, not deleted).

---

## A. Product / Scope Decisions

- **D-001** — Project is **analytics & reporting only**. No transactional alumni-management features. _[PRD]_
- **D-002** — **No AI/LLM/chatbot/RAG/recommender/confidence-scoring/predictive** features in MVP. _[PRD]_
- **D-003** — Alumni validation is **strict and explicit**: must contain "Universitas Airlangga" + 1 of 5 approved programs, else excluded. _[PRD]_
- **D-004** — Approved programs are fixed at 5 (Data Science Tech, Industrial Eng, Electrical Eng, Nanotech Eng, Robotics & AI Eng). _[PRD]_
- **D-005** — MVP data sources limited to LinkedIn, Verified Alumni Records, Tracer Study Reports. Self-submitted/IKA forms deferred. _[PRD]_

## B. Data Model / Behavior Decisions

- **D-006** — Data is **snapshot-based**, refreshed **quarterly**; no real-time sync. _[PRD]_
- **D-007** — **Snapshot Quarter** is a global filter dimension → data must be time-versioned/labeled by quarter. _[PRD, inferred from filter list]_
- **D-008** — **Company Normalization** is an in-scope, required capability (consistency is a success metric). _[PRD]_
- **D-009** — **Industry Classification** is an in-scope, required capability (consistency is a success metric). _[PRD]_
- **D-010** — **Geographic Mapping** (Country + City) is in-scope. _[PRD]_

## C. Architecture / Stack Decisions

- **D-011** — Frontend: **Next.js + TypeScript + TailwindCSS + Shadcn UI**, charts via **ECharts**. _[PRD]_
- **D-012** — Backend: **FastAPI + SQLAlchemy**. _[PRD]_
- **D-013** — Database: **PostgreSQL hosted on Supabase**. _[PRD]_
- **D-014** — Deployment surfaces: **Vercel + Railway + Supabase** (allocation per service not yet specified — see OPEN_QUESTIONS). _[PRD]_

## D. Non-Functional / Target Decisions

- **D-015** — Target scale: **100–1,000 alumni** (small dataset). _[PRD]_
- **D-016** — Success requires **faculty-ready reporting** and **dashboard responsiveness**. _[PRD]_

---

## E. Schema / Data-Model Decisions _(Artifact #2)_

- **D-017** — **Company normalization** via canonical `COMPANY` + `COMPANY_ALIAS` (many raw aliases → one canonical company). _[Schema v1]_
- **D-018** — **Industry** modeled as its own table (`industry_id, sector_name, taxonomy_code`) and attached at **COMPANY level** (industry derived per company, not per career record). _[Schema v1]_
- **D-019** — **Geography normalized** in `LOCATION` (country/province/city/region); COMPANY links to a location. _[Schema v1]_
- **D-020** — **Career history preserved** via `CAREER_RECORD` (1 alumnus → N records); exactly **one current role** enforced by partial unique index on `is_current`. _[Schema v1]_
- **D-021** — **Snapshot model:** `REFRESH_SNAPSHOT` metadata + `career_record.snapshot_id`; point-in-time reporting at **career-record grain**. Master entities are NOT versioned. _(Resolves Q-002, Q-003)_ _[Schema v1]_
- **D-022** — **Provenance** tracked via `CAPTURE_SOURCE` (source_type, confidence_level): LinkedIn / Verified Faculty Record / Tracer Study / Alumni Form. _[Schema v1]_
- **D-023** — **Alumni identity** keyed by `public_id` (UUID, unique) and **unique `linkedin_url`**. _(Partially resolves Q-014)_ _[Schema v1]_
- **D-024** — **Validation operationalized** via `STUDY_PROGRAM.is_ftmm_valid` + `ALUMNI.validation_status`; **curator-controlled, deterministic** (Data Curator role). _(Partially resolves Q-004)_ _[Schema v1]_
- **D-025** — **Audit layer** `AUDIT_LOG` records table/record/action + old/new values + changed_by + timestamp. _[Schema v1]_
- **D-026** — **RBAC security layer:** `APP_USER`, `ROLE`, `PERMISSION`, `ROLE_PERMISSION`; roles = Admin, Data Curator, Faculty Viewer, Read Only. _[Schema v1]_
- **D-027** — **Workload profile:** read-heavy, quarterly batch writes, low write concurrency; future scale 5,000+. _[Schema v1]_
- **D-028** — **Indexing strategy** defined (PKs + FK/filter columns + search indexes on linkedin_url & canonical_company_name). _[Schema v1]_
- **D-029** — **Constraints:** unique `public_id`, `linkedin_url`, canonical company name; partial unique = one active career record per alumnus. _[Schema v1]_
- **D-030** — **Extended non-goals:** no event-driven architecture, microservices, or real-time streaming pipelines (in addition to prior AI/LLM exclusions). All matching/validation deterministic & curator-controlled. _(Extends D-001/D-002)_ _[Schema v1]_

---

## F. System Architecture Decisions _(Artifact #3)_

- **D-031** — **Topology:** Users → Next.js → FastAPI → Supabase PG. Frontend never writes to DB directly; **all access via FastAPI**, the single business-logic gateway. _(AD-001)_ _[Arch v1]_
- **D-032** — **Authentication:** Supabase Auth issues **JWT**; FastAPI verifies JWT + role before authorizing API access. Roles: Admin / Data Curator / Faculty Viewer / Read Only. _(AD-002)_ _[Arch v1]_
- **D-033** — **Ingestion is a Manual Import Workflow** through FastAPI: Import → Validation → Normalization → **Deduplication** → Snapshot Assignment → Storage. _[Arch v1]_
- **D-034** — **Quarterly refresh workflow** stages defined: Collection → Validation → Normalization → Snapshot Creation → Dashboard Refresh. No real-time. _(reaffirms D-006/AD-003)_ _[Arch v1]_
- **D-035** — **Deployment mapping:** Frontend=Vercel, Backend=Railway, DB=Supabase; env vars managed per platform. _(Resolves Q-001)_ _[Arch v1]_
- **D-036** — **Security model:** backend owns business rules; DB not directly exposed; audit logging on; RBAC; least privilege. _[Arch v1]_
- **D-037** — **Monorepo** layout: `frontend/`, `backend/`, `database/`, `docs/`, `scripts/`. _[Arch v1]_
- **D-038** — **Explicit scale exclusions:** no Kubernetes, event streaming, Kafka, CQRS, microservices, or distributed systems. MVP 100–1,000; future 5,000+. _(extends D-030; AD-007/008/009)_ _[Arch v1]_
- **D-039** — **Architecture principles** adopted: simplicity, maintainability-over-optimization, deterministic processing, validation-first, read-heavy optimization, no real-time, no AI-driven decisions. _(AD-010)_ _[Arch v1]_

**Reaffirmations (no new ID):** AD-003→D-006/D-021; AD-004→D-024; AD-005→D-008/D-017; AD-006→D-002.

---

## G. Blocker-Resolution Decisions — APPROVED _(post Artifact #3 review; from BLOCKER_RESOLUTION_PROPOSAL.md)_

- **D-040** — **University handling:** add `university` text column on `ALUMNI` (default "Universitas Airlangga") for audit; the explicit-match rule is enforced in the **curator validation workflow**, not as a relational entity. _(Resolves C-3/Q-016)_
- **D-041** — **Provenance FK (career):** add `source_id` (FK → CAPTURE_SOURCE), **NOT NULL**, on `CAREER_RECORD`. _(Resolves C-4/Q-015, R-014)_
- **D-042** — **Industry/Sector shape:** keep one flat `INDUSTRY` table with **`industry_name`** (granular) + **`sector_name`** (parent grouping). Industry Distribution groups by industry_name; Sector Breakdown groups by sector_name. _(Resolves C-5/Q-018)_
- **D-043** — **Auth/authz split:** **Supabase Auth = authentication** (login + JWT carrying user UUID); **app DB = authorization** (`APP_USER` keyed by Supabase UUID → ROLE/ROLE_PERMISSION). No roles in JWT claims. _(Resolves C-6/Q-026, R-018)_
- **D-044** — **Alumni identity:** `public_id` (UUID) is the system identity; `linkedin_url` is **nullable + partial-unique**. Deterministic candidate-match signal = normalized(full_name) + study_program_id + graduation_year. _(Resolves Q-014, R-012, R-006)_
- **D-045** — **Deduplication:** two-tier deterministic + curator-confirmed — (1) exact `linkedin_url` auto-link; (2) candidate key → curator review queue. No fuzzy/AI matching. _(Resolves Q-025, R-020)_
- **D-046** — **Provenance FK (alumni):** add `source_id` (FK → CAPTURE_SOURCE) on `ALUMNI` as primary provenance; validation history via AUDIT_LOG. _(Resolves Q-019)_
- **D-047** — **Validation states:** `validation_status` ∈ {`pending`, `validated`, `rejected`}; only `validated` rows enter analytics; `rejected` retained for audit/anti-churn. _(Resolves Q-017)_
- **D-048** — **Employment semantics:** current CAREER_RECORD ⇒ Employed; none ⇒ Not Reported/Unknown. Dashboard shows "Employed vs Not Reported"; **no unemployment rate asserted** (documented data limitation). No schema change. _(Resolves Q-020)_
- **D-049** — **Source-trust tier:** `confidence_level` redefined as a **static, curator-assigned trust tier** (Verified > Tracer > LinkedIn); never computed, never auto-decides inclusion. Optional rename `trust_level`. _(Resolves C-2/Q-024, R-013)_
- **D-050** — **LinkedIn posture:** platform performs **no in-app scraping**; LinkedIn enters only as a manually/offline-collected dataset; faculty-verified/tracer data preferred as system of record. _(Partial — external legal sign-off outstanding: R-001)_
- **D-051** — **PII safeguards:** RBAC + least privilege, **data minimization**, retention aligned to quarterly snapshots, AUDIT_LOG accountability. _(Partial — institutional legal basis/consent outstanding: R-002)_

### Schema deltas implied by Section G (additive to Schema v1)
`ALUMNI`: + `university`, + `source_id` (FK), `linkedin_url` → nullable + partial-unique, `validation_status` → enum{pending,validated,rejected}. · `CAREER_RECORD`: + `source_id` (FK, NOT NULL). · `INDUSTRY`: + `industry_name`. · `CAPTURE_SOURCE`: `confidence_level` semantics fixed (static tier). · `APP_USER`: keyed by Supabase user UUID. · Cleanups: `COMPANY.country` (Q-021), declared FK targets (Q-023).

---

### Decision Log Notes
- No decisions superseded. D-040–D-051 **extend** Schema v1 / Arch v1 additively (no rebuild).
- **D-023 refined by D-044** (linkedin_url no longer the sole identity; now nullable + partial-unique).
- All §2A *technical* blockers closed. D-050/D-051 carry **external legal preconditions** (R-001/R-002) that are institutional, not design, actions.
