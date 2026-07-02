# RISKS.md

> Risks surfaced from artifacts, with likely impact and area. Not mitigation planning yet (that waits for "Architecture is finalized").
> **Last updated:** Blocker Resolution Pass — APPROVED (post Artifact #3 review)
> Severity: 🔴 high · 🟡 medium · 🟢 low · ✅ closed

---

## Data Acquisition & Legal

- **R-001** 🟡 **REMAINING — external legal precondition.** Platform-level exposure reduced by no-in-app-scraping (D-050), but the **legal/ToS posture of the offline collection requires FTMM institutional/legal sign-off** before production ingestion. Not a design item.
- **R-002** 🟡 **REMAINING — external legal precondition.** Technical safeguards adopted (D-051: RBAC, minimization, retention, audit). The **UU PDP legal basis/consent is an institutional determination** outstanding before storing real alumni PII. Not a design item.

## Data Quality & Coverage

- **R-003** 🟡 **(accepted, monitored)** Strict explicit-match rule may undercount alumni. Inclusion rule (D-003) is intentional; curators monitor coverage. **Accepted MVP limitation.**
- **R-004** 🟡 **(accepted, monitored)** Manual deterministic normalization is effortful and inconsistency-prone. Mitigated by curator workflow + alias/trust structures; tooling is a build-time improvement. (See R-015)
- **R-005** 🟢 _(mitigated, D-045/D-049)_ **Source reconciliation conflicts** now handled by curator-confirmed merge with source-trust-tier tie-breaker. Residual = normal curator judgment. (Q-010 resolved)
- **R-006** ✅ _(closed, D-044/D-045)_ **Identity resolution** — stable `public_id` UUID + deterministic candidate-match + curator dedup queue. (Q-014, Q-025 resolved)

## Architecture & Model

- **R-007** 🟢 _(downgraded)_ **Snapshot/versioning model now defined** (D-021) — risk of late retrofit largely mitigated for career facts. Residual concern (non-versioned master entities) moved to **R-011**.
- **R-008** 🟡 **(accepted MVP, document)** **Three-vendor deployment** ops surface (secrets/CORS/latency). Acceptable at small scale; document env/secret handling during build. (Q-001 resolved the mapping.)

## Scope & Expectation

- **R-009** 🟢 **(deferred / V2)** Alumni network growth not surfaced in MVP UI. Tracked with C-1 for V2.
- **R-010** 🟢 **(build-time)** Industry-standard / seniority / role taxonomies to be finalized during build (Q-005–Q-009); structure is settled (D-042).

## New — Architecture & Model _(Artifact #2)_

- **R-011** 🟡 **(accepted / V2)** Only career facts are snapshot-versioned; master-entity reclassification is retroactive. **Accepted MVP limitation**; versioning deferred to V2. (Q-022)
- **R-012** ✅ _(closed, D-044)_ `linkedin_url` no longer the identity — now nullable + partial-unique; `public_id` UUID is the key.
- **R-013** ✅ _(closed, D-049)_ `confidence_level` bounded as a static source-trust tier; no scoring drift.
- **R-014** ✅ _(closed, D-041)_ `source_id` FK (NOT NULL) added to CAREER_RECORD; provenance integrity restored.
- **R-015** 🟡 **(accepted, monitored)** **Curator workload** grows slightly under the resolution set (review queue, pending→validated, trust-tier seeding). Load-bearing for data quality but small at 100–1,000. No tooling mandated for MVP. (Reinforces R-004)

## New — Deployment & Architecture _(Artifact #3)_

- **R-016** 🟡 **(accepted MVP)** Single-gateway SPOF (FastAPI on Railway). Acceptable at MVP scale; redundancy/HA deferred to V2. Configure health checks during build.
- **R-017** 🟡 **(accepted MVP)** Supabase vendor concentration (Auth + DB). Acceptable for MVP; failover deferred to V2.
- **R-018** ✅ _(closed, D-043)_ Auth/authz responsibilities split cleanly — Supabase authenticates, app DB authorizes (APP_USER keyed by Supabase UUID). Drift reduced to low-volume user provisioning.
- **R-019** 🟢 **(deferred / V2)** No caching for read-heavy aggregations; live SQL accepted for MVP scale.
- **R-020** ✅ _(closed, D-045)_ Deterministic two-tier dedup + curator review queue defined.

---

## Tracked Contradictions

- **C-1** 🟡 **(deferred to V2)** **Growth vs snapshot UI gap.** No growth/trend page in MVP scope; alumni-count growth modeling deferred. Tracked as a V2 enhancement, not an implementation blocker. → R-009.
- **C-2** ✅ **CLOSED (D-049).** `confidence_level` fixed as a static source-trust tier; complies with the no-confidence-scoring non-goal.
- **C-3** ✅ **CLOSED (D-040).** University captured as a stored attribute + curator-enforced rule (no entity in MVP).
- **C-4** ✅ **CLOSED (D-041).** `source_id` FK (NOT NULL) added to CAREER_RECORD.
- **C-5** ✅ **CLOSED (D-042).** Flat INDUSTRY with `industry_name` + `sector_name` serves both PRD widgets.
- **C-6** ✅ **CLOSED (D-043).** Supabase authenticates; app DB authorizes; APP_USER keyed by Supabase UUID.
