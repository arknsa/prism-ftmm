# BLOCKER_RESOLUTION_PROPOSAL.md

> Principal Architect proposals to clear the §2A Must-Resolve blockers from the Architecture Readiness Report.
> **Scope guardrails honored:** no whole-system redesign, no new features, one recommendation each.
> **Target context:** 100–1,000 alumni · FastAPI · Supabase PostgreSQL · quarterly manual refresh · university MVP.
> **Status:** PROPOSAL — not yet folded into DECISIONS.md. Canonical registers update only on your approval.
> Schema changes below are described in prose (no DDL/code per instruction).

---

## C-3 / Q-016 — University not modeled

1. **Issue.** The inclusion rule requires an explicit "Universitas Airlangga" match, but no university field or entity exists in the schema.
2. **Why it blocks.** Validation and audit can't reference the university half of the rule; inclusion can't be justified or queried.
3. **Recommendation (MVP).** Do **not** build a UNIVERSITY entity. Add a single `university` text column on `ALUMNI` (defaulting to "Universitas Airlangga") for provenance/audit, and enforce the actual rule in the **curator validation workflow**: a row can only reach `validated` if the curator confirms UNAIR + an approved program.
4. **Consequences.** Rule enforcement is deterministic and curator-controlled; the stored attribute makes inclusion auditable; zero relational overhead. Trade-off: the university check lives partly in process rather than as a hard constraint — acceptable for a single-university curated MVP. If FTMM later spans multiple universities, promote the column to a lookup table (V2).
5. **Status: Resolved (MVP).**

---

## C-4 / Q-015 — Missing `source_id` FK on CAREER_RECORD

1. **Issue.** The architecture declares `CAPTURE_SOURCE 1→N CAREER_RECORD`, but `CAREER_RECORD` has no source column.
2. **Why it blocks.** Provenance and audit goals are unmeetable; the schema is internally inconsistent.
3. **Recommendation (MVP).** Add `source_id` (FK → `CAPTURE_SOURCE`), **NOT NULL**, on `CAREER_RECORD`. Every employment fact must carry a known source.
4. **Consequences.** Per-record provenance restored; trivial migration; aligns with audit goals. NOT NULL forces the import to always assign one of the three known sources — which it can.
5. **Status: Resolved.**

---

## C-5 / Q-018 — Industry vs Sector (flat table vs two-level need)

1. **Issue.** The PRD needs both *Industry Distribution* and *Sector Breakdown*, but `INDUSTRY` is one flat table that currently carries only `sector_name` (no granular industry name).
2. **Why it blocks.** It determines the shape of a core reference table.
3. **Recommendation (MVP).** Keep a **single flat `INDUSTRY` table with two label columns**: add `industry_name` (granular) alongside the existing `sector_name` (the parent grouping). "Industry Distribution" groups by `industry_name`; "Sector Breakdown" groups by `sector_name`. No separate SECTOR table, no self-referencing hierarchy.
4. **Consequences.** Both PRD widgets are satisfied with simple GROUP BYs; reference table stays tiny. Trade-off: `sector_name` is denormalized (repeated across industries) — negligible at this scale. A normalized Industry→Sector hierarchy remains a clean V2 promotion if ever needed.
5. **Status: Resolved.**

---

## C-6 / Q-026 — Two identity/role systems

1. **Issue.** Auth uses Supabase Auth (JWT) while the schema defines a custom APP_USER/ROLE/PERMISSION/ROLE_PERMISSION layer; no source of truth was declared.
2. **Why it blocks.** RBAC can't be built without knowing where identity and roles live.
3. **Recommendation (MVP).** **Split responsibilities:** Supabase Auth owns *authentication only* (login + JWT containing the user UUID `sub`). The app DB owns *authorization*: `APP_USER` is keyed by the Supabase user UUID and holds the role; FastAPI verifies the JWT, looks up `APP_USER`, and enforces RBAC via `ROLE`/`ROLE_PERMISSION`. Do not duplicate roles into Supabase custom claims.
4. **Consequences.** One identity source (Supabase), one authorization source (app DB), cleanly separated. The only sync point is user provisioning (create a Supabase user + an `APP_USER` row), a low-volume admin action for a handful of staff. Drift risk drops to near-zero. `PERMISSION`/`ROLE_PERMISSION` can be statically seeded for the 4 roles.
5. **Status: Resolved.**

---

## Q-014 / R-012 — Alumni identity key (non-LinkedIn sources)

1. **Issue.** `linkedin_url` is unique, but Tracer-/Verified-only alumni have no LinkedIn URL, so it can't be the identity.
2. **Why it blocks.** It defines the primary key and dedup behavior of the whole registry.
3. **Recommendation (MVP).** Make **`public_id` (UUID) the system identity**. Make `linkedin_url` **nullable** with a **partial unique index** (unique only when present). For human dedup, define a deterministic *candidate-match signal*: normalized(`full_name`) + `study_program_id` + `graduation_year`.
4. **Consequences.** Every alumnus has a stable identity regardless of source; LinkedIn uniqueness still enforced where it exists; identity decisions stay curator-controlled and AI-free. Trade-off: the candidate signal isn't perfectly unique (namesakes) → curator adjudicates (see Q-025). Acceptable at 100–1,000.
5. **Status: Resolved** (paired with Q-025).

---

## Q-025 / R-020 — Deterministic deduplication rule

1. **Issue.** The ingestion flow asserts a Deduplication step with no method, and AI matching is excluded.
2. **Why it blocks.** Ingestion correctness and identity integrity depend on it.
3. **Recommendation (MVP).** **Two-tier, curator-confirmed deterministic dedup at import:** (1) exact `linkedin_url` match (when present) → auto-link/skip; (2) deterministic candidate key (normalized name + program + grad year) → push to a **curator review queue** for confirm-merge or keep-separate. Normalization = lowercase, trim, collapse whitespace, strip honorifics. No fuzzy/AI matching.
4. **Consequences.** Deterministic, auditable, and small enough to review each quarter (folds into existing curator workload). Trade-off: non-obvious duplicates (variant spelling + no LinkedIn) may slip through — an accepted MVP limitation.
5. **Status: Resolved.**

---

## Q-019 — Alumni-level provenance

1. **Issue.** `CAPTURE_SOURCE` links only to `CAREER_RECORD`; how an *alumnus* entered the registry isn't recorded.
2. **Why it blocks.** Can't record or audit the origin/validation provenance of a registry entry.
3. **Recommendation (MVP).** Add `source_id` (FK → `CAPTURE_SOURCE`) on `ALUMNI` to record the **primary source** that established the record. Validation history (who/when, pending→validated) is already covered by `AUDIT_LOG.changed_by`.
4. **Consequences.** Each alumnus carries a primary provenance; validation changes are auditable. Trade-off: only one primary source is stored even if multiple corroborate — multi-source corroboration is a V2 enhancement.
5. **Status: Resolved.**

---

## Q-017 — `validation_status` value set

1. **Issue.** The allowed states for `ALUMNI.validation_status` were never defined, yet every dashboard filters on validity.
2. **Why it blocks.** It is the inclusion gate for all analytics.
3. **Recommendation (MVP).** Fixed three-state set (Postgres enum or CHECK): **`pending`**, **`validated`**, **`rejected`**. Only `validated` rows appear in dashboards/analytics. `pending` = imported, awaiting curator confirmation. `rejected` = reviewed and excluded (wrong program/university), retained for audit and to prevent re-import churn.
4. **Consequences.** Unambiguous inclusion rule; rejected records preserved without polluting analytics. Trade-off: curator must advance `pending → validated` each quarter (already expected workload).
5. **Status: Resolved.**

---

## Q-020 — Unemployed / unknown employment representation

1. **Issue.** `CAREER_RECORD` stores only employment, but "Employment Distribution" implies non-employed buckets — and absence of data isn't the same as unemployment.
2. **Why it blocks.** It defines the semantics (and possible schema) behind a PRD widget.
3. **Recommendation (MVP).** No schema change. Adopt a **documented semantic rule**: an alumnus with a current `CAREER_RECORD` ⇒ **Employed**; an alumnus with none ⇒ **Not Reported / Unknown**. The dashboard reports **"Employed vs Not Reported"**, and explicitly does **not** assert an unemployment rate.
4. **Consequences.** Honest representation that avoids fabricating unemployment from missing data (which LinkedIn-sourced data can't support anyway); zero schema cost. Trade-off: no true unemployment metric in MVP — an accepted, documented data limitation.
5. **Status: Resolved** (as a semantic rule + stated limitation).

---

## C-2 / Q-024 — `confidence_level` vs "no confidence scoring"

1. **Issue.** A `confidence_level` field sits against the explicit non-goal of confidence scoring.
2. **Why it blocks.** Non-goal compliance, and the field's meaning, must be settled before it ships.
3. **Recommendation (MVP).** Reinterpret it as a **static, curator-assigned source-trust tier** set once per `CAPTURE_SOURCE` row at seed time (e.g., Verified Faculty Record = high, Tracer Study = medium, LinkedIn = lower). It is reliability metadata for *human* conflict resolution — never computed, never used to auto-decide inclusion. Renaming to `trust_level` is optional but clarifying.
4. **Consequences.** Fully compliant with "no confidence scoring" (nothing is scored or inferred); gives curators a consistent tie-breaker when sources disagree. Trade-off: must be documented as static/non-automated to prevent future scope creep toward scoring.
5. **Status: Resolved.**

---

## R-001 — LinkedIn data legal / ToS posture

1. **Issue.** How LinkedIn profile data is obtained carries Terms-of-Service and legal exposure.
2. **Why it blocks.** It's a compliance gate before the primary dataset is collected or stored.
3. **Recommendation (MVP).** Keep the platform out of automated scraping (the architecture already imports a **manually, offline-collected** dataset — preserve that). Treat LinkedIn as supplementary public-profile information, and prefer **faculty-verified / tracer data as the system of record** where available. Route the actual collection method through **FTMM institutional/legal sign-off** and document it.
4. **Consequences.** Platform-level ToS exposure is minimized; responsibility for the collection method sits with a documented institutional process. Trade-off: depends on an external legal/ethics review.
5. **Status: Partially Resolved** — architectural posture set; **institutional legal sign-off is external and outstanding.** *(I'm not a lawyer; this needs professional/institutional review.)*

---

## R-002 — PII / Indonesian Personal Data Protection (UU PDP)

1. **Issue.** Centralizing personal alumni career data triggers consent, retention, and access obligations.
2. **Why it blocks.** It's a compliance gate for handling personal data at all.
3. **Recommendation (MVP).** Apply technical safeguards now: (a) RBAC + least privilege (already decided); (b) **data minimization** — store only fields the dashboards need (name, program, grad year, employer, role, location, optional LinkedIn URL); avoid sensitive categories; (c) a documented **retention policy** aligned to quarterly snapshots; (d) `AUDIT_LOG` for accountability; (e) establish the **legal basis/consent** for analytics/accreditation use via FTMM.
4. **Consequences.** Technical posture aligns with UU PDP principles (minimization, access control, accountability). Trade-off: technical safeguards are not a substitute for a formal legal basis / DPIA. The legal determination is institutional.
5. **Status: Partially Resolved** — technical safeguards recommended; **legal basis/consent is external and outstanding.** *(Not legal advice; requires institutional review.)*

---

## Summary

| Blocker | Status |
|---------|--------|
| C-3 / Q-016 — University modeling | ✅ Resolved (MVP) |
| C-4 / Q-015 — Missing source FK | ✅ Resolved |
| C-5 / Q-018 — Industry/Sector shape | ✅ Resolved |
| C-6 / Q-026 — Auth/role source of truth | ✅ Resolved |
| Q-014 / R-012 — Alumni identity key | ✅ Resolved |
| Q-025 / R-020 — Deterministic dedup | ✅ Resolved |
| Q-019 — Alumni provenance | ✅ Resolved |
| Q-017 — validation_status set | ✅ Resolved |
| Q-020 — Employment/unknown semantics | ✅ Resolved |
| C-2 / Q-024 — confidence_level meaning | ✅ Resolved |
| R-001 — LinkedIn legal posture | 🟡 Partially Resolved (external sign-off pending) |
| R-002 — PII / UU PDP | 🟡 Partially Resolved (legal basis pending) |

**10 Resolved · 2 Partially Resolved.**

The two partials are not architectural gaps — they are **institutional/legal actions** outside what design can settle. Every *technical* blocker has a single, MVP-scoped decision. On your approval I will fold these into DECISIONS.md, flip the corresponding OPEN_QUESTIONS/RISKS entries, and re-score the readiness report.
