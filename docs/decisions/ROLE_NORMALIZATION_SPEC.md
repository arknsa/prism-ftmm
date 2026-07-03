# ROLE_NORMALIZATION_SPEC.md — Artifact A5

> **Status:** Approved  
> **Required by:** Phase 3 Session S4 (P3.9 — role & seniority assignment)  
> **Resolves:** Q-008 (role/position normalization approach — build-time detail)  
> **Decision basis:** D-020 (role_title stored on CAREER_RECORD), D-039 (deterministic), D-002 (no AI/inference), D-030 (no real-time, no complex processing).  
> **Date:** 2026-07-01

---

## 1. Decision: Store Raw, Clean Lightly

**Role titles are stored verbatim (after light cleaning) on `CAREER_RECORD.role_title`.** No mapping to a canonical role family taxonomy occurs at ingest time.

**Rationale:**
- Role title diversity is extremely high and context-dependent; any taxonomy imposed at ingest creates noise rather than signal (consistent with D-039 — deterministic only).
- The curator assigns industry/seniority at Phase 4; role_title is a free-form label used for display and director search, not for aggregation.
- Dashboard aggregations (Phase 5) aggregate by **seniority** (assigned deterministically via A4) and **company/industry** (assigned via company normalization), not by role_title — so role_title canonicalization is not required for any approved analytic.
- Curators can search/filter by raw role_title text in the Alumni Directory (Phase 6, P6.9).
- A full role taxonomy (mapping "Software Engineer" → "Engineering" family) is a Phase 4+ curator enrichment, not an ingest pipeline requirement.

**No role taxonomy table is introduced.** The `CAREER_RECORD.role_title` column already exists as `VARCHAR(500)`.

---

## 2. Light Cleaning Rules (deterministic)

The following transforms are applied to `raw_role_title` before storing as `role_title`. All transforms are deterministic string operations — no inference.

| Step | Operation |
|------|-----------|
| 1 | Strip leading/trailing whitespace |
| 2 | Collapse internal whitespace runs to a single space |
| 3 | Preserve original casing (title case is NOT forced — "CTO" stays "CTO") |
| 4 | If blank/None after stripping → store `None` |

**Output:** `role_title: str | None` on the career-record candidate.

---

## 3. Relationship to Seniority (A4)

The seniority classification (Artifact A4) runs on the **raw** `role_title` before cleaning (or equivalently on the cleaned version — the cleaning is non-semantic and does not affect keyword matching). The two operations are independent:

```
raw_role_title → [clean] → role_title (stored)
raw_role_title → [A4 keyword match] → seniority (stored separately)
```

---

## 4. Testable Invariants

1. `None` → stored as `None`.
2. `"  Software Engineer  "` → stored as `"Software Engineer"`.
3. `"Data  Scientist"` → stored as `"Data Scientist"`.
4. `"CTO"` → stored as `"CTO"` (casing preserved).
5. `"   "` (whitespace only) → stored as `None`.
6. Same input → same output (deterministic).

---

## 5. Not in Scope

- Role family taxonomy (Engineering / Product / Design / etc.) — deferred, not a Phase 3–5 analytic requirement.
- Fuzzy/AI role normalization (permanent non-goal, D-002).
- Role title validation or rejection (any non-blank string is a valid role_title).
- Cross-source role deduplication (handled at the alumni-dedup level, Phase 4).
