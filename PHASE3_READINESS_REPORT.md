# Phase 3 Readiness Report — Import → Validation → Normalization

**Project:** FTMM Alumni Intelligence Dashboard  
**Phase under review:** 3 — Import → Validation → Normalization (Epics E, F, G)  
**Review date:** 2026-07-01  
**Reviewer:** Claude Code (planning review — no application code generated)  
**Verdict:** **CONDITIONAL GO** — engineering foundation is ready; **three decision artifacts and one execution plan must be authored before implementation starts.**

---

## 0. Executive Summary

Phase 3 turns a raw synthetic dataset into staged, validated, normalized candidate records — the first four stages of the D-033 ingestion pipeline (Import → Validation → Normalization), stopping short of dedup/snapshot commit (Phase 4).

**The build substrate is ready.** All schema tables Phase 3 writes to exist with the correct D-040–D-051 deltas already applied. The models were deliberately authored in Phase 1 with Phase-3 nullability (`career_record.seniority`, `company.industry_id/location_id`). The audit contract (`write_audit_entry`) is defined and uses a caller-owned transaction boundary — exactly what import commits need. Every RBAC permission Phase 3 endpoints must guard on (`import:run`, `alumni:write`, `alumni:validate`, `company:write`, `career:write`) is already defined in the role-permission matrix and enforceable via the Phase 2 `require_permission` factory.

**What blocks a clean start is not code — it is undecided scope.** Phase 3 normalization tasks (P3.4, P3.7, P3.8, P3.9) require deterministic rules whose *content* is not yet decided:

- **Seniority ladder** (Q-007) — P3.9 cannot deterministically map titles → seniority without a defined ladder.
- **Program-name variant → canonical mapping** (Q-005) — P3.4 cannot map free-text program strings without a variant table.
- **Industry taxonomy standard** (Q-006) — affects `taxonomy_code`; partially mitigated (seed data already picked a custom taxonomy).
- **Role/position normalization approach** (Q-008) and **geographic normalization source** (Q-009) — P3.9/P3.8 need a decided approach.

These are exactly the artifacts the handoff (§12) lists as **"prepare before Phase 3."** They do not yet exist as authored documents. Per Golden Rule #1 ("if a task seems to need something not decided, **stop and ask** — do not invent scope"), the implementation agent must not invent a seniority ladder or a program-variant table. **The operator must supply/approve these first.**

Additionally, **`PHASE3_EXECUTION_PLAN.md` does not exist.** Phases 0, 1, and 2 each had one; Phase 3 does not. It should be authored (session/task breakdown) before implementation, consistent with prior phases.

---

## 1. Dependency Verification

### 1.1 Roadmap task-level dependencies (Phase 3 tasks P3.1–P3.9)

| Task | Depends on | Dependency status | Notes |
|------|-----------|-------------------|-------|
| P3.1 Staging tables/models | P1.4 (CAREER_RECORD) | ✅ SATISFIED | Core schema migrated (0001–0008). |
| P3.2 Import parser service | P3.1, P1.11 (CAPTURE_SOURCE seed) | ⚠️ CODE-READY / DECISION-GAP | P3.1 is intra-phase; CAPTURE_SOURCE seed script exists. File-format detail is build-time (Q-010 note). |
| P3.3 Import entry points (UI + CLI) | P3.2, P1.14 (audit contract) | ✅ SATISFIED | Audit contract defined; `scripts/imports/` dir exists. Resolves Q-027 (build-time). |
| P3.4 Program/university matcher | P3.2, P1.10 (STUDY_PROGRAM seed) | 🔴 DECISION-BLOCKED | Seed exists (5 valid + sentinel), but **program-variant→canonical mapping rules (Q-005) undecided.** |
| P3.5 Validation-status assignment | P3.4 | ✅ SATISFIED (downstream of P3.4) | `validation_status` enum + `is_ftmm_valid` in place. |
| P3.6 Company normalization | P3.2, P1.2 (COMPANY/ALIAS) | ✅ SATISFIED | COMPANY + COMPANY_ALIAS migrated; alias uniqueness constraint present. |
| P3.7 Industry classification | P3.6, P1.13 (INDUSTRY seed) | ⚠️ CODE-READY / MINOR-GAP | 21-row INDUSTRY seed exists. `taxonomy_code` standard (Q-006) still nominally open but seed already commits to a custom taxonomy. |
| P3.8 Location normalization | P3.2, P1.13 (LOCATION seed) | ⚠️ CODE-READY / DECISION-GAP | LOCATION table + seed exist. **Canonical country/city list + remote handling (Q-009) undecided.** |
| P3.9 Role & seniority assignment | P3.2 | 🔴 DECISION-BLOCKED | `role_title` + nullable `seniority` in place, but **seniority ladder (Q-007) and role-normalization approach (Q-008) undecided.** |

### 1.2 Cross-phase prerequisites (Phases 0–2)

| Prerequisite | Roadmap ref | Status | Evidence |
|--------------|-------------|--------|----------|
| Monorepo + tooling | P0.1–P0.3 | ✅ | `backend/fastapi-app`, `frontend/nextjs-app`, `scripts/imports`, `docs/` all present. |
| FastAPI skeleton + settings + logging + `/health` | P0.4 | ✅ | App factory, config, health endpoint verified in Phase 2 review. |
| SQLAlchemy + Alembic wiring | P0.5 | ✅ | `migrations/env.py` + 8 migrations present. |
| API client layer (frontend) | P0.7 | ✅ | `lib/api-client.ts` with `apiFetch` / `apiFetchWithAuth`. |
| Cloud infra (Supabase/Railway/Vercel) | P0.8–P0.11 | ⛔ OPERATOR-PENDING | Requires operator accounts. **Not a code blocker for Phase 3 build**, but blocks live import runs against a real DB. |
| Full schema migrated | P1.1–P1.9 | ✅ | Migrations 0001–0008; deltas verified in models (see §3). |
| Reference/seed data | P1.10–P1.13 | ✅ | Seed scripts for study programs, capture sources, industry, location, RBAC. |
| Audit-write contract | P1.14 | ✅ | `app/services/audit.py::write_audit_entry` (caller-owned txn). |
| Backend auth (JWT verify + APP_USER resolver) | P2.1–P2.2 | ✅ | `dependencies/auth.py`; 24 tests pass. |
| RBAC enforcement utility | P2.3 | ✅ | `dependencies/rbac.py::require_permission` factory. |
| User provisioning | P2.4 | ✅ | `services/user_provisioning.py`. |
| Frontend auth + role gating | P2.5–P2.6 | ✅ | Login, proxy, AuthProvider, permission-based nav. |

**Conclusion:** every *engineering* prerequisite from Phases 0–2 that Phase 3 code depends on is satisfied. The only Phase 0–2 gap (P0.8–P0.11 cloud provisioning) is operator-dependent and blocks *execution against a live DB*, not *implementation*.

---

## 2. Database Schema Readiness

All tables Phase 3 reads or writes exist, with Phase-3-relevant nullability deliberately in place.

| Table | Phase 3 usage | Ready? | Phase-3-aware design |
|-------|---------------|--------|----------------------|
| `study_program` | Matcher target (P3.4) | ✅ | `is_ftmm_valid` flag; seeded with 5 valid + sentinel. |
| `alumni` | Written on import; validated (P3.4/P3.5) | ✅ | `validation_status` enum defaults `pending`; `source_id` NOT NULL; `university` default; `public_id` UUID auto. |
| `company` | Normalization target (P3.6/P3.7) | ✅ | `industry_id`/`location_id` **nullable** — curator assigns later (P4.10). `canonical_name` unique. |
| `company_alias` | Raw→canonical map (P3.6) | ✅ | `alias_name` unique; `source_id` FK. |
| `industry` | Classification (P3.7) | ✅ | `industry_name` + `sector_name` (D-042); seeded 21 rows + catch-all. |
| `location` | Normalization (P3.8) | ✅ | country NOT NULL, province/city/region nullable (partial resolution supported). |
| `career_record` | Written on import (P3.6/P3.9) | ✅ | `seniority` **nullable** (P3.9 assigns); `snapshot_id` **nullable** (P4.5 assigns); `source_id` NOT NULL. |
| `capture_source` | Provenance tagging | ✅ | `trust_tier` static (D-049); seeded 4 sources. |
| `refresh_snapshot` | Not written until P4 | ✅ (present) | Exists; Phase 3 leaves `snapshot_id` NULL. |
| `audit_log` | Written on import (P3.3) | ✅ | JSONB old/new; `changed_by` nullable for CLI/system imports. |
| **Staging tables** | P3.1 creates them | 🟢 TO-BUILD | This is the *first new schema work of Phase 3* — a new migration (0009+) for staging/import-batch tables. No conflict with existing schema. |

**Migration state:** `0001_baseline` → `0008_career_record_indexes_constraints`. Phase 3 adds the staging migration(s). Migrations run cleanly in Phase 1/2 validation. No schema rework required — deltas are additive per D-040–D-051.

---

## 3. API Readiness

| Concern | Status | Notes |
|---------|--------|-------|
| FastAPI app factory + router registration | ✅ | `main.py` registers health, me, users routers; adding import/validation/normalization routers is mechanical. |
| Typed request/response schema pattern | ✅ | Pydantic schemas established (`schemas/auth.py`, `schemas/users.py`). Phase 3 adds import/validation schemas. |
| Service-layer pattern | ✅ | `services/` established (`audit.py`, `user_provisioning.py`); Phase 3 adds parser/matcher/normalizer services. |
| Frontend API client for authed calls | ✅ | `apiFetchWithAuth` ready for Phase 4 curator UI; Phase 3 backend is CLI + endpoint. |
| File-upload endpoint capability | 🟢 TO-BUILD | FastAPI supports `UploadFile`; no prior upload endpoint exists yet. Size/type limits are a P7.8 hardening item but basic validation should land in P3.3. |
| OpenAPI contract outline for curation endpoints | 🔴 MISSING | Handoff §12 lists "API contract / OpenAPI outline for curation + aggregation endpoints" as a before-Phase-3/5 artifact. Not authored. Recommended before P3.3. |

---

## 4. Authentication Dependencies — ✅ READY

- JWT verification (`verify_jwt`) and `get_current_user` (APP_USER resolver loading permissions) are implemented and tested (Phase 2, 85 tests).
- Import CLI (`scripts/imports/`) runs **outside** the request auth context — `audit_log.changed_by` is nullable precisely to support system/script imports (verified in `audit.py` model docstring). This is by design (D-043 sync point + P1.14 contract).
- Import **UI upload endpoint** (P3.3) will sit behind `require_permission("import:run")` — the guard factory exists.

No authentication work is required before Phase 3.

---

## 5. Authorization Dependencies — ✅ READY

The `ROLE_PERMISSION_MATRIX.md` (Phase 1, authoritative) already defines every permission Phase 3 needs, seeded via `seed_rbac.py`:

| Phase 3 operation | Guard permission | Granted to | Defined? |
|-------------------|------------------|-----------|----------|
| Run import (UI) | `import:run` | Admin, Data Curator | ✅ |
| Create/update alumni | `alumni:write` | Admin, Data Curator | ✅ |
| Validate/reject alumni | `alumni:validate` | Admin, Data Curator | ✅ |
| Create/update company + alias | `company:write` | Admin, Data Curator | ✅ |
| Create/update career records | `career:write` | Admin, Data Curator | ✅ |

`require_permission("<perm>")` returns uniquely-named DI guards (Phase 2). No new permission needs to be invented for Phase 3 — a strong signal the RBAC design anticipated the ingestion pipeline. **No authorization work required before Phase 3.**

---

## 6. Snapshot Model Readiness — ✅ READY (consumed in Phase 4, not Phase 3)

- `refresh_snapshot` table exists; `career_record.snapshot_id` is a nullable FK.
- **Phase 3 intentionally does not assign `snapshot_id`** — records stay unsnapshotted candidates until the Phase 4 commit stage (P4.5). The nullable FK + `ondelete="SET NULL"` design supports this exactly.
- No snapshot work is required or permitted in Phase 3 (guardrail: Phase 3 exit = "not yet committed under a snapshot").

---

## 7. Audit Logging Readiness — ✅ READY

- `write_audit_entry(session, ...)` is defined (P1.14) and **does not flush/commit** — the caller owns the transaction so an audit row commits atomically with the mutation it describes. This is the correct primitive for P3.3 (import writes to staging + audit).
- `old_values`/`new_values` JSONB; `changed_by` nullable for CLI imports.
- Full audit *wiring across all mutations* is a Phase 4 task (P4.6), but Phase 3 imports (P3.3) must already write audit entries per the roadmap ("both writing to staging + audit (J)"). The contract supports this today.

**One watch-item:** Phase 3 is the *first consumer* of `write_audit_entry`. Expect to validate the caller-owned-transaction pattern end-to-end (add entry → flush mutation + audit together → commit) with a real import in P3.3. Budget a test for it.

---

## 8. Missing Artifacts Required Before Phase 3

Ordered by severity. Items 1–3 are **decision inputs the operator must supply/approve** (Golden Rule #1 forbids inventing them).

| # | Artifact | Severity | Blocks | Source requirement |
|---|----------|----------|--------|--------------------|
| 1 | **Seniority ladder** (defined levels + deterministic title→level rules) | 🔴 BLOCKER | P3.9 | Handoff §12; Q-007 (🟡 open) |
| 2 | **Program-name variant → canonical mapping** (deterministic table of known variants → 5 programs) | 🔴 BLOCKER | P3.4 | Handoff §12; Q-005 (🟡 open) |
| 3 | **Role/position normalization approach** (how noisy titles canonicalize) | 🟡 HIGH | P3.9 (partial) | Q-008 (🟡 open) |
| 4 | **Industry taxonomy standard** for `taxonomy_code` | 🟢 LOW | P3.7 (cosmetic) | Q-006 (🟡 open) — *mitigated:* seed already commits to a custom taxonomy; `taxonomy_code` is nullable. |
| 5 | **Geographic canonical list + remote/multi-location handling** | 🟡 MEDIUM | P3.8 | Q-009 (🟡 open) |
| 6 | **Import file-format spec** (CSV/XLSX column contract per source) | 🟡 MEDIUM | P3.2 | Q-010 note (build-time) |
| 7 | **API/OpenAPI outline** for curation endpoints | 🟡 MEDIUM | P3.3 | Handoff §12 |
| 8 | **`PHASE3_EXECUTION_PLAN.md`** (session/task breakdown, like prior phases) | 🟡 PROCESS | Orderly execution | Prior-phase convention (S1–S5 plans existed) |
| 9 | **Synthetic data spec/generator** (small sample to exercise the pipeline) | 🟢 LOW | Testing P3.x | Handoff §12 ("anytime from Phase 3"); formal generator is P7.2. A minimal fixture suffices for Phase 3 tests. |

> **Deterministic-only guardrail:** every rule above must be a lookup table or explicit rule set — **no fuzzy/AI matching** (Golden Rule #3, D-045). The seniority ladder and program-variant map are *data*, not inference. This is why they can (and should) be decided as artifacts before code.

---

## 9. Recommended Build Order (within Phase 3)

Derived from roadmap dependencies (§P3.1–P3.9) and the parallelization note ("company / location / role-seniority normalizers are independent after P3.2").

```
Pre-work (decisions/artifacts §8 items 1–8)
      │
      ▼
P3.1  Staging tables + import-batch model         [new migration 0009]
      │
      ▼
P3.2  Import parser service (CSV/XLSX → staging)   [needs file-format spec #6]
      │
      ├─────────────┬───────────────┬──────────────────┐
      ▼             ▼               ▼                  ▼
P3.3 Entry points  P3.6 Company     P3.8 Location      P3.9 Role & seniority
  (UI + CLI,        normalization    normalization      [needs ladder #1,
   audit-wired)     │                [needs geo #5]      approach #3]
      │             ▼
      │           P3.7 Industry classification
      │             (attach company→industry)
      ▼
P3.4  Program/university matcher                   [needs variant map #2]
      │
      ▼
P3.5  Validation-status assignment (pending/validated/rejected)
      │
      ▼
Phase 3 exit: synthetic CSV → staged, validated, normalized candidates
              (NOT snapshot-committed — that is Phase 4)
```

**Parallelizable after P3.2** (solo micro-batching): P3.6→P3.7 (company/industry), P3.8 (location), P3.9 (role/seniority) are mutually independent. P3.4→P3.5 (validation) depends only on P3.2 + the program seed.

---

## 10. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **R-P3.1 — Inventing undecided scope.** Agent fabricates a seniority ladder or program-variant map instead of stopping. | Medium | High (violates Golden Rule #1; produces unapproved business logic) | Author artifacts §8.1–§8.3 **before** starting P3.4/P3.9. Report explicitly flags this. |
| **R-P3.2 — Non-deterministic drift.** A "just make it work" normalizer sneaks in fuzzy matching. | Medium | High (violates D-045/Golden Rule #3) | All matchers must be lookup-table/rule-based. Add tests asserting deterministic output for fixed inputs. |
| **R-P3.3 — Strict-match undercount.** Deterministic program match rejects legitimate variants not in the map. | High | Medium (accepted MVP limitation, §11 handoff) | Route non-matches to `pending` for curator review — never silently drop. Curator gate is the safety net. |
| **R-P3.4 — Audit pattern first real use.** Caller-owned transaction misused (audit committed without mutation, or vice versa). | Medium | Medium | End-to-end test of import → audit atomicity in P3.3. |
| **R-P3.5 — No live DB.** P0.8–P0.11 unprovisioned; import can't run against real Supabase. | High (current) | Low for build (tests use fixtures/SQLite-compatible or transactional Postgres); High for demo | Build + test against local/transactional Postgres or test fixtures; live run waits on operator provisioning. |
| **R-P3.6 — File-format ambiguity.** Parser built against assumed columns that differ from real source exports. | Medium | Medium | Decide file-format spec (§8.6) with sample synthetic files first. |
| **R-P3.7 — Staging-schema churn.** Staging model under-designed, reworked in Phase 4 dedup. | Low | Medium | Design staging with import-batch metadata + raw + normalized columns up front (roadmap P3.1 intent). |
| **R-001 / R-002 legal (standing).** Real PII ingestion blocked. | Certain | N/A for MVP build | Synthetic data only (Golden Rule #6). Unchanged by Phase 3. |

---

## 11. Critical Implementation Sequence (condensed)

1. **Decide & document** artifacts §8 items 1–3 (blockers) and 5–7 (high/medium) → get operator approval.
2. **Author `PHASE3_EXECUTION_PLAN.md`** (session breakdown, e.g. S1 staging+parser, S2 validation, S3 normalization, S4 review).
3. **P3.1** staging migration (additive; 0009+).
4. **P3.2** parser service against the agreed file-format spec + minimal synthetic fixtures.
5. **P3.3** dual entry points (UI upload guarded by `import:run`; CLI in `scripts/imports/`) — both audit-wired; validate audit atomicity.
6. **P3.6→P3.7** company + industry normalization; **P3.8** location; **P3.9** role/seniority (using the approved ladder).
7. **P3.4→P3.5** program/university matcher + validation-status assignment; non-matches → `pending`.
8. **Tests** for every deterministic rule (fixed input → fixed output) and import→audit atomicity.

---

## 12. Estimated Implementation Sessions

Phase 3 is one of the two **heaviest** phases (roadmap complexity rollup: 4×M + 4×L). Estimating in the same session grain as Phases 1–2 (each roadmap task ≈ ½–1 session; L tasks may span more):

| Session | Scope | Tasks | Weight |
|---------|-------|-------|--------|
| **S1** | Staging + import parser | P3.1, P3.2 | M + L |
| **S2** | Import entry points (UI + CLI) + audit wiring | P3.3 | M |
| **S3** | Company + industry normalization | P3.6, P3.7 | L + M |
| **S4** | Location + role/seniority normalization | P3.8, P3.9 | M + M |
| **S5** | Program/university matcher + validation status | P3.4, P3.5 | L + M |
| **S6** | Phase 3 integration test pass + Phase 3 review | (test/hardening) | M |

**Estimate: 6 implementation sessions** (vs 5 for Phase 2), reflecting the two L-weighted normalizer/matcher tasks and the deterministic-rule test burden. This assumes decision artifacts §8 are resolved **before** S1 — otherwise S5 (matcher) and S4 (seniority) stall.

---

## 13. Recommended Review Checkpoints

Consistent with the Phase 2 cadence (per-session engineering review + phase-completion review):

| Checkpoint | When | Focus |
|-----------|------|-------|
| **CP-0 Artifact sign-off** | Before S1 | Operator approves seniority ladder, program-variant map, geo list, file-format spec, API outline. **Gate: no P3.4/P3.9 code until ladder + variant map approved.** |
| **CP-1 Post-S1** | After parser | Staging schema shape; parser determinism; no fuzzy logic; batch metadata captured. |
| **CP-2 Post-S2** | After entry points | Import→staging→audit atomicity; `import:run` guard; CLI + UI parity. |
| **CP-3 Post-S3/S4** | After normalizers | Each normalizer deterministic (table-driven); curator-assignable fields left nullable where intended (company industry/location); no premature snapshot assignment. |
| **CP-4 Post-S5** | After matcher | Strict program+university match; non-matches → `pending` (never dropped); only valid program+UNAIR → `validated`-eligible (D-047). |
| **CP-5 Phase 3 completion review** | After S6 | Full pipeline on synthetic CSV → staged/validated/normalized candidates; all validators green; scope compliance vs DECISIONS.md; **confirm nothing committed under a snapshot**; generate `PHASE3_COMPLETION_REPORT.md`. |

---

## 14. Readiness Verdict

**CONDITIONAL GO.**

- **Engineering foundation (schema, API scaffold, auth, authz, snapshot model, audit contract): READY.** No rework required; all Phase 0–2 code dependencies satisfied; the schema and models were authored with Phase 3 in mind.
- **Blocking condition:** author and obtain operator approval for the **seniority ladder** (Q-007) and **program-name variant→canonical mapping** (Q-005) before implementing P3.9 and P3.4. Strongly recommended alongside: geographic canonical list (Q-009), import file-format spec, curation API/OpenAPI outline, and **`PHASE3_EXECUTION_PLAN.md`**.
- **Operator-pending (non-blocking for build, blocking for live runs):** P0.8–P0.11 cloud provisioning; live migration + seed against real Supabase.
- **Standing constraint:** synthetic data only (R-001/R-002); all matching deterministic and curator-controlled.

**Do not begin Phase 3 implementation until CP-0 (artifact sign-off) clears the two 🔴 blockers.**

---

*No application code was generated in this review. This is a planning artifact only.*
