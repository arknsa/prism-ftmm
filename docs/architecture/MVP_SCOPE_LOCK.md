# MVP_SCOPE_LOCK.md

> Consolidates already-decided scope from Artifacts #1–#3. This is a **scope lock**, not an architecture sign-off.
> **Locking scope ≠ "Architecture is finalized."** Implementation remains gated (see ARCHITECTURE_READINESS_REPORT.md).
> **Basis:** PRD (#1), DB Schema v1 (#2), System Architecture v1 (#3). No new features introduced here.

---

## 1. Final MVP Scope (locked)

### Product surface
- **Six dashboard pages:** Executive Overview, Career Outcomes, Company Analytics, Industry Analytics, Geographic Analytics, Alumni Directory.
- **Global filters:** Study Program, Graduation Year, Industry, Company, Country, Snapshot Quarter.

### Data & domain
- **Alumni Registry** with **strict, deterministic validation** (Universitas Airlangga **AND** one of 5 approved FTMM programs).
- **Company normalization** via canonical company + alias mapping.
- **Industry classification** at company level (taxonomy-coded).
- **Geographic mapping** (country/province/city/region).
- **Career history** with one current role per alumnus; full history preserved.
- **Quarterly snapshot model** (point-in-time at career-record grain).

### Workflows
- **Manual import workflow** from three sources: LinkedIn dataset, Verified Alumni Records, Tracer Study reports — processed through FastAPI (Import → Validation → Normalization → Deduplication → Snapshot Assignment → Storage).
- **Quarterly refresh cycle** (no real-time).

### Platform & cross-cutting
- **Stack:** Next.js/TS/Tailwind/Shadcn/ECharts (Vercel) · FastAPI/SQLAlchemy (Railway) · PostgreSQL (Supabase).
- **FastAPI = single business-logic gateway**; DB not directly exposed.
- **Auth:** Supabase Auth → JWT → FastAPI role verification.
- **RBAC:** Admin, Data Curator, Faculty Viewer, Read Only.
- **Audit logging** of important changes.
- **Monorepo** structure.
- **Target scale:** 100–1,000 alumni.

> ⚠️ Items above are *scoped in*, but several depend on **Must-Resolve blockers** (see readiness report) that affect how they are built. Scope is locked; design is not.

---

## 2. Deferred Features (V2)

- **Alumni network growth / trend visualizations** — a PRD objective with no MVP page or supporting model (C-1, R-009).
- **Alumni self-submitted forms** and **IKA Alumni forms** (PRD future sources).
- **Additional dashboard analytics** beyond the six locked pages.

## 3. Deferred Architecture (V2 / not-now)

- Caching / materialized views and read-performance hardening (Q-028, R-019).
- Gateway redundancy / high-availability for the single FastAPI gateway (R-016).
- Multi-region / vendor-failover strategy (R-017).
- Anything to support the **5,000+** future scale tier.

## 4. Deferred Data-Model Enhancements (V2)

- **Snapshot-versioning of master entities** (COMPANY / INDUSTRY / STUDY_PROGRAM) for true point-in-time classification (R-011, Q-022).
- **Alumni-count growth modeling** (snapshot linkage on ALUMNI) (C-1).
- **Two-level Industry→Sector hierarchy** *if* the C-5 decision is to model both levels rather than collapse to one (candidate enhancement; the keep/collapse decision itself is a Must-Resolve, not deferrable).

## 5. Explicit Non-Goals (permanent — not "deferred," excluded)

From PRD + Schema + Architecture, consistently restated:
- AI assistants, chatbots, RAG, recommendation systems, LLM features.
- AI-assisted matching / AI verification.
- **Confidence scoring** *(note: a `confidence_level` field exists in schema — flagged as contradiction C-2, pending a keep/define/drop decision).*
- Advanced predictive analytics.
- Real-time synchronization / streaming pipelines.
- Microservices, event-driven architecture, Kafka, CQRS, Kubernetes, distributed systems.

---

## 6. Scope-Lock Caveat

This lock fixes **what** the MVP includes. It does **not** certify that the design is buildable as drawn. Five structural contradictions (C-2…C-6) and a cluster of identity/provenance/auth open questions still gate implementation — enumerated and classified in `ARCHITECTURE_READINESS_REPORT.md`.
