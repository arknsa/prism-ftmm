# ARCHITECTURE_READINESS_REPORT.md

> Pre-implementation review by Principal DB Architect / Principal Backend Engineer / Technical Reviewer.
> **Inputs:** PRD (#1), DB Schema v1 (#2), System Architecture v1 (#3) and the tracked C/Q/R registers.
> **Mandate:** assess readiness and identify blockers only. No redesign, no code, no solutions.

---

## 0. POST-RESOLUTION UPDATE (APPROVED blocker resolutions D-040–D-051)

> The original review (§1–§5 below) is retained for history. This section supersedes the scores and determination after all §2A *technical* blockers were resolved and approved.

### Recalculated readiness scores

| Dimension | Was | **Now** | Why it moved |
|-----------|:---:|:------:|--------------|
| **Architecture Completeness** | 62 | **85** | 5 of 6 contradictions closed (C-2…C-6); only V2 deferral (C-1) + 2 external legal preconditions remain. |
| **Database Readiness** | 65 | **88** | Identity, provenance FKs, validation enum, industry/sector shape, university attribute all settled. Residual = build-time cleanups + deferred V2 versioning. |
| **Backend Readiness** | 55 | **80** | Auth/authz model, deterministic dedup, validation/inclusion semantics now defined. Remaining is implementation (API contracts) + build-time taxonomies. |
| **Frontend Readiness** | 70 | **82** | Industry/Sector and employment semantics resolved (all six pages now data-backed); growth page consciously deferred. Depends on aggregation APIs (implementation). |
| **Deployment Readiness** | 60 | **70** | Auth ambiguity removed; ops posture documented as accepted-MVP. Still lacks CI/CD & secret-management detail (build-time, non-blocking). |

### Determination (updated)

## ✅ READY FOR IMPLEMENTATION — with one non-design precondition

No **design** work remains: every technical Must-Resolve blocker is closed (D-040–D-051), and all other open items are classified **build-time** or **V2** and are non-blocking. Engineering may begin (schema migrations reflecting the §G deltas, backend contracts, frontend).

**Remaining blockers (the only items still gating *production data*):**
- **R-001** — LinkedIn collection legal/ToS sign-off (institutional). 
- **R-002** — PII / UU PDP legal basis & consent (institutional).

These are **institutional/legal actions, not architecture**. Recommendation: **build may start now**; **ingestion of real alumni PII should not go live until R-001/R-002 are cleared.** Synthetic/sample data can be used for development in the meantime.

> Note: This report records readiness. It is **not** the "Architecture is finalized" trigger — implementation *planning* still awaits that explicit instruction.

---

## 1. Triage Method (original review — retained for history)

Every contradiction (C), open question (Q), and risk (R) is placed in exactly one bucket:

- **MUST RESOLVE BEFORE BUILD** — structural (schema shape, identity, auth) or legal/compliance gates; getting these wrong forces a rebuild.
- **CAN RESOLVE DURING BUILD** — procedures, taxonomies, value sets, and cleanups definable without structural change.
- **CAN DEFER TO V2** — future-scale, growth, or hardening items not required for the locked MVP.
- **RESOLVED / CLOSED** — already answered by a later artifact.

---

## 2. Master Classification

### 2A. MUST RESOLVE BEFORE BUILD (blockers)

| ID(s) | Item | Why it gates build |
|-------|------|--------------------|
| **C-3 / Q-016** | University not modeled | Core validation rule (D-003) requires explicit "Universitas Airlangga"; no field/entity exists. Affects schema + inclusion logic. |
| **C-4 / Q-015 / R-014** | Declared-but-missing `source_id` FK on CAREER_RECORD | Schema is internally inconsistent; provenance/audit goals unmeetable as drawn. |
| **C-5 / Q-018** | Industry vs Sector (flat table vs two-level PRD need) | Determines INDUSTRY table shape; structural. |
| **C-6 / Q-026 / R-018** | Two identity/role systems (Supabase Auth vs APP_USER RBAC) | Auth + RBAC cannot be built without a single source of truth. |
| **Q-014 / R-006 / R-012** | Alumni identity key (esp. non-LinkedIn sources) | Foundational PK/dedup behavior; `linkedin_url` cannot key Tracer/Verified-only people. |
| **Q-025 / R-020** | Deterministic deduplication rule | Architecture asserts a Dedup step with no defined, AI-free method; depends on identity decision. |
| **Q-019** | Alumni-level provenance | CAPTURE_SOURCE links only to CAREER_RECORD; alumnus origin/validation provenance unmodeled. |
| **Q-017** | `validation_status` value set & inclusion semantics | Gates which rows appear in every dashboard; needs definition before queries are built. |
| **Q-020** | Unemployed / unknown employment representation | May require an explicit status concept; affects "Employment Distribution" and schema. |
| **C-2 / Q-024 / R-013** | `confidence_level` keep / define / drop | Low effort, but a non-goal-compliance decision that touches a shipped schema field. |
| **R-001** | LinkedIn data legal/ToS posture | Compliance gate before collecting/storing the primary dataset. |
| **R-002** | PII / Indonesian UU PDP (consent, retention, access) | Compliance gate for storing personal alumni data centrally. |

**Blocker count: 12 clusters.**

### 2B. CAN RESOLVE DURING BUILD

| ID(s) | Item | Note |
|-------|------|------|
| Q-004 / R-004 / R-015 | Validation mechanism + curator tooling/workload | Process & tooling, iterable. |
| Q-005 | Program-name variant → canonical mapping | Mapping table/procedure. |
| Q-006 | Industry taxonomy *standard* choice | Column exists; pick standard during build. |
| Q-007 | Seniority taxonomy / ladder | `seniority` column exists. |
| Q-008 | Role-title normalization | `role_title` stored raw. |
| Q-009 | Geographic normalization source | LOCATION exists. |
| Q-010 / R-005 | Source ingestion formats + merge/precedence rule | Rule-definable (depends on identity decision). |
| Q-011 | LinkedIn import mechanism (technical) | Manual dataset import; build-time. |
| Q-012 | Graduation-year capture confirmation | Field exists; verify population. |
| Q-021 | Redundant `COMPANY.country` cleanup | Denormalization tidy-up. |
| Q-023 | Unspecified FK targets (`changed_by`, alias `source`) | Declare during schema build. |
| Q-027 | Import trigger surface (admin UI vs scripts) | Operational decision. |
| Q-028 | Aggregation strategy (live SQL acceptable for MVP) | Decide live-aggregation now; revisit at scale. |
| R-003 | Strict-match undercount | Monitor; likely an **accepted MVP limitation**. |
| R-008 / R-016 / R-017 | Three-vendor ops / gateway SPOF / vendor concentration | Acceptable at MVP scale; configure & document. |
| R-010 | Taxonomy definitions outstanding | Folds into Q-006/Q-007. |

### 2C. CAN DEFER TO V2

| ID(s) | Item |
|-------|------|
| C-1 / R-009 | Alumni network growth page + model |
| R-011 / Q-022 | Snapshot-versioning of master entities (point-in-time classification) |
| R-019 | Caching / read-performance hardening |
| — | 5,000+ scale provisioning |

### 2D. RESOLVED / CLOSED

| ID(s) | Resolution |
|-------|-----------|
| Q-001 | Deployment mapping fixed (D-035). |
| Q-002 / Q-003 | Snapshot model & grain defined (D-021). |
| Q-013 | Career history model defined (D-020). |
| R-007 | Largely closed by D-021 (residual in R-011). |

---

## 3. Readiness Scores (0–100)

> Scores reflect *implementation-readiness as documented*, not eventual quality. Rationale given for each.

| Dimension | Score | Rationale |
|-----------|:----:|-----------|
| **Architecture Completeness (overall)** | **62** | Principles, topology, flows, deployment, and non-goals are coherent and internally consistent at the conceptual level. Held down by 5 open contradictions (C-2…C-6) and a 12-cluster Must-Resolve set spanning identity, provenance, and auth. |
| **Database Readiness** | **65** | Strong foundation: entities, relationships, indexing, constraints, snapshot model, audit/RBAC tables. Blocked by structural gaps: missing source FK (C-4), no university modeling (C-3), flat Industry/Sector (C-5), non-LinkedIn identity (Q-014), alumni provenance (Q-019), `validation_status` set (Q-017), unemployed representation (Q-020). |
| **Backend Readiness** | **55** | Responsibilities and request/ingest flows are defined, but the *deterministic procedures* that are the core of this system (validation, normalization, **dedup**) are unspecified, and the auth/role model is ambiguous (C-6). No API contracts yet. |
| **Frontend Readiness** | **70** | Most concrete area: pages, widgets, filters, and stack are well-specified and mostly map to available data. Dependent on undefined aggregation APIs; two widgets affected by open items (Industry/Sector C-5; growth C-1). |
| **Deployment Readiness** | **60** | Platform mapping, monorepo, and per-platform env management are decided. Missing: CI/CD, secret-management detail, gateway SPOF / vendor-concentration posture (R-016/R-017), migration & runtime ops. Acceptable for MVP but undocumented. |

---

## 4. Determination

### 🟥 NEEDS ADDITIONAL DESIGN WORK

The architecture is **conceptually sound and internally consistent at the principle level**, and product/deployment scope is lockable. However, it is **not ready for implementation** because the Must-Resolve set includes **structural and foundational blockers** that would force rework if built around:

1. **Identity & deduplication** (Q-014 / Q-025) — the data model's primary keys and merge behavior are not settled for non-LinkedIn sources.
2. **Authentication/authorization source of truth** (C-6) — two competing user/role systems.
3. **Schema-correctness contradictions** (C-3 university, C-4 missing FK, C-5 industry/sector).
4. **Inclusion & status semantics** (Q-017, Q-019, Q-020) that gate every dashboard query.
5. **Legal/compliance gates** (R-001 LinkedIn posture, R-002 PII/UU PDP) that gate data handling itself.

These are decisions, not implementations — most can be closed quickly — but they must be closed **before** schema migrations and backend contracts are written.

### Path to "Ready for Implementation"
Resolve the 12 Must-Resolve clusters in §2A (in particular the identity/dedup/auth trio and the legal gates). Can-Resolve-During-Build and V2 items do **not** block the start of implementation once §2A is closed.

---

## 5. Reviewer Notes
- No contradictions were solved in this review (per mandate); each remains owned in `OPEN_QUESTIONS.md` / `RISKS.md`.
- Scores are documentary-readiness judgments and will move as artifacts are added or blockers closed.
- This report does **not** constitute the "Architecture is finalized" trigger.
