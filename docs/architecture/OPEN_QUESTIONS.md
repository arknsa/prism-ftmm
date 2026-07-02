# OPEN_QUESTIONS.md

> Unresolved decisions, ambiguities, and contradictions awaiting later artifacts or stakeholder input.
> **Last updated:** Blocker Resolution Pass — APPROVED (post Artifact #3 review)
> Status legend: 🔴 blocking · 🟡 needs clarification · 🟢 minor / track-only · ✅ resolved
> **Note:** All §2A technical blockers approved in BLOCKER_RESOLUTION_PROPOSAL.md are now closed below (decisions D-040–D-051). Remaining open items are non-blocking (build-time or V2) except the two external legal preconditions R-001/R-002.

---

## Deployment & Infrastructure

- **Q-001** ✅ **RESOLVED (Artifact #3 / D-035).** Next.js → Vercel, FastAPI → Railway, Postgres → Supabase. Env vars managed per platform.

## Snapshot / Versioning Model

- **Q-002** ✅ **RESOLVED (Artifact #2 / D-021).** Snapshots stored as `REFRESH_SNAPSHOT` metadata; `CAREER_RECORD.snapshot_id` tags each employment fact; historical records preserved (append-style). Point-in-time reporting supported at career-record grain. *Caveat: master entities not versioned → see Q-022 / R-011.*
- **Q-003** ✅ **RESOLVED (Artifact #2).** Snapshot granularity = **career-record level**.

## Alumni Validation Mechanism

- **Q-004** 🟡 **PARTIALLY RESOLVED (D-024).** Actor is now defined: the **Data Curator** role; validation is curator-controlled + deterministic, recorded in `ALUMNI.validation_status`, and gated by `STUDY_PROGRAM.is_ftmm_valid`. **Still open:** the concrete matching procedure/tooling (how raw LinkedIn text becomes a canonical program/company decision).
- **Q-005** 🟡 **Program name normalization** — LinkedIn free-text program names will vary ("Robotics & AI", "Teknik Robotika dan AI", etc.). How are variants mapped to the 5 canonical programs without fuzzy/AI matching?

## Taxonomies & Reference Data

- **Q-006** 🟡 **(non-blocking, build-time)** Industry **taxonomy standard** (LinkedIn / NAICS / ISIC / custom) still to be chosen for `taxonomy_code`. *(The Industry/Sector shape issue is resolved by D-042.)*
- **Q-007** 🟡 **Seniority taxonomy undefined.** "Seniority Distribution" needs a defined ladder (e.g., Intern/Junior/Mid/Senior/Lead/Exec) and a deterministic way to derive it from job titles.
- **Q-008** 🟡 **Role/position normalization** — "Current Roles" needs canonicalization; raw LinkedIn titles are noisy. Approach unspecified.
- **Q-009** 🟢 **Geographic normalization source** — country/city canonical list and handling of remote/multi-location alumni unspecified.

## Source Integration

- **Q-010** ✅ **RESOLVED (D-045/D-049).** Conflict precedence is **curator-confirmed**, using the static **source-trust tier** (Verified > Tracer > LinkedIn) as tie-breaker; dedup is deterministic (D-045). Ingestion *file formats* remain a build-time detail (non-blocking).
- **Q-011** ✅ **RESOLVED at platform level (D-050).** The platform performs **no in-app scraping**; LinkedIn data enters only as a manually, offline-collected dataset via the import workflow. *The legal posture of that external collection remains the open precondition R-001.*

## Data Fields

- **Q-012** 🟢 **Graduation Year** is a global filter but not listed in validation fields — confirm it is reliably captured per alumnus.
- **Q-013** ✅ **RESOLVED (D-020).** Full employment history is kept (1 alumnus → N `CAREER_RECORD`s); exactly one `is_current`. History preserved across snapshots.

## Identity & Dedup

- **Q-014** ✅ **RESOLVED (D-044).** `public_id` (UUID) is the system identity; `linkedin_url` is **nullable + partial-unique** (unique only when present). Non-LinkedIn alumni get a UUID identity; a deterministic candidate signal (normalized name + program + grad year) feeds curator dedup. See D-045.

---

## New — from Artifact #2 (DB Schema v1)

- **Q-015** ✅ **RESOLVED (D-041).** `source_id` FK (→ CAPTURE_SOURCE), NOT NULL, added to `CAREER_RECORD`.
- **Q-016** ✅ **RESOLVED (D-040).** `university` text column on `ALUMNI` (default "Universitas Airlangga") for audit; rule enforced in curator validation workflow. No UNIVERSITY entity in MVP.
- **Q-017** ✅ **RESOLVED (D-047).** `validation_status` ∈ {`pending`, `validated`, `rejected`}; only `validated` appears in analytics; `rejected` retained for audit/anti-churn.
- **Q-018** ✅ **RESOLVED (D-042).** Flat `INDUSTRY` with two label columns: `industry_name` (granular → Industry Distribution) and `sector_name` (parent → Sector Breakdown). No separate sector table.
- **Q-019** ✅ **RESOLVED (D-046).** `source_id` FK (→ CAPTURE_SOURCE) added to `ALUMNI` as primary provenance; validation history via AUDIT_LOG.
- **Q-020** ✅ **RESOLVED (D-048).** Semantic rule: current `CAREER_RECORD` ⇒ Employed; none ⇒ Not Reported/Unknown. Dashboard reports "Employed vs Not Reported"; no unemployment rate asserted (documented data limitation). No schema change.
- **Q-021** 🟢 **(non-blocking, build-time)** Redundant `COMPANY.country` to be cleaned up during schema build.
- **Q-022** 🟡 **(deferred to V2)** Master-entity snapshot-versioning. MVP accepts point-in-time accuracy at career-record grain only. (R-011)
- **Q-023** 🟢 **(non-blocking, build-time)** Declare FK targets: `AUDIT_LOG.changed_by` → APP_USER; `COMPANY_ALIAS.source` → CAPTURE_SOURCE.
- **Q-024** ✅ **RESOLVED (D-049).** `confidence_level` redefined as a **static, curator-assigned source-trust tier** (never computed, never auto-deciding inclusion). Optional rename to `trust_level`.

---

## New — from Artifact #3 (System Architecture v1)

- **Q-025** ✅ **RESOLVED (D-045).** Two-tier deterministic dedup: (1) exact `linkedin_url` auto-link; (2) candidate key (normalized name + program + grad year) → curator review queue. No fuzzy/AI matching.
- **Q-026** ✅ **RESOLVED (D-043).** Supabase Auth owns **authentication** (login + JWT with user UUID); app DB owns **authorization** (`APP_USER` keyed by Supabase UUID → ROLE/ROLE_PERMISSION). No role duplication in JWT claims.
- **Q-027** 🟡 **(non-blocking, build-time)** Import trigger surface (admin UI vs `scripts/imports/`) to be decided during build; both must write to AUDIT_LOG.
- **Q-028** 🟡 **(non-blocking, build-time)** Live SQL aggregation accepted for MVP scale; caching/materialized views deferred (R-019/V2).
