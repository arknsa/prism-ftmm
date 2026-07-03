# SENIORITY_LADDER_SPEC.md — Artifact A4

> **Status:** Approved  
> **Required by:** Phase 3 Session S4 (P3.9 — role & seniority assignment)  
> **Resolves:** Q-007 (seniority ladder definition — build-time detail)  
> **Decision basis:** D-020 (career history preserved, seniority captured), D-039 (deterministic processing), D-002 (no AI/inference).  
> **Date:** 2026-07-01

---

## 1. Design Constraints

- **Deterministic only** (D-039, D-002). No inference, no ML, no fuzzy matching.
- Seniority is assigned from the raw `role_title` string via keyword matching against a priority-ordered rule table.
- When no level is determinable, the result is `"Other"` — never NULL, never omitted.
- The ladder is stored entirely in application code as constants (no DB table needed at this scale).
- The curator can override seniority via the Phase 4 curator UI (P4.10) — the pipeline assignment is the *initial* value, not a permanent lock.

---

## 2. Seniority Ladder (canonical levels)

| Level (canonical) | Description |
|-------------------|-------------|
| `Intern` | Student internship, magang, trainee, apprentice |
| `Entry` | Fresh graduate, junior, staff, associate (non-management) |
| `Mid` | Mid-level individual contributor; 2–5 year implied experience signals |
| `Senior` | Senior individual contributor; specialist, expert, principal |
| `Lead` | Team lead, tech lead, squad lead; leads a small team without full people-management |
| `Manager` | Manager, head-of, supervisor; formal direct-report responsibility |
| `Director` | Director, VP, SVP, EVP; divisional leadership |
| `Executive` | C-level: CEO, CTO, CFO, COO, CPO, CXO; founder |
| `Other` | Catch-all when no keyword match applies |

---

## 3. Keyword Matching Rules

The algorithm applies **first-match wins** in the priority order listed below. Each rule checks whether the **lowercased, whitespace-normalised** role title *contains* any of the listed tokens.

| Priority | Level | Trigger tokens (any substring match on normalized title) |
|----------|-------|----------------------------------------------------------|
| 1 | `Executive` | `chief`, `ceo`, `cto`, `cfo`, `coo`, `cpo`, `cxo`, `founder`, `co-founder`, `cofounder`, `president` |
| 2 | `Director` | `director`, `vice president`, `vp `, ` vp`, `svp`, `evp`, `head of`, `head, ` |
| 3 | `Manager` | `manager`, `supervisor`, `superintendent`, `head`, `kepala` |
| 4 | `Lead` | `lead`, `team lead`, `tech lead`, `squad lead`, `chapter lead`, `tribe lead` |
| 5 | `Senior` | `senior`, `sr.`, `sr `, `principal`, `specialist`, `expert`, `architect`, `consultant` |
| 6 | `Intern` | `intern`, `magang`, `trainee`, `apprentice`, `practicum`, `praktek` |
| 7 | `Entry` | `junior`, `jr.`, `jr `, `associate`, `staff`, `analyst`, `graduate`, `fresh`, `entry` |
| 8 | `Mid` | `mid`, `ii`, `iii`, `iv` (as whole word), `engineer`, `developer`, `scientist`, `designer`, `researcher` |
| 9 | `Other` | (default — no earlier rule matched) |

**Matching semantics:**
- Normalize: strip, lowercase, collapse whitespace.
- Test each row in priority order; return the first level that matches.
- Substring match (not whole-word) except where noted (`"ii"`, `"iii"`, `"iv"` must be surrounded by whitespace or string boundaries to avoid false matches inside words).
- If the title is blank/None → `"Other"`.

---

## 4. Testable Invariants

1. `None` or blank title → `"Other"`.
2. `"Software Engineer"` → `"Mid"` (rule 8 — "engineer").
3. `"Senior Software Engineer"` → `"Senior"` (rule 5 — "senior", before rule 8).
4. `"Junior Data Analyst"` → `"Entry"` (rule 7 — "junior").
5. `"Magang"` → `"Intern"` (rule 6 — "magang").
6. `"CTO"` → `"Executive"` (rule 1 — "cto").
7. `"Engineering Manager"` → `"Manager"` (rule 3 — "manager").
8. `"Tech Lead"` → `"Lead"` (rule 4 — "lead").
9. `"Vice President of Engineering"` → `"Director"` (rule 2 — "vice president").
10. `"Freelance Photographer"` → `"Other"` (no rule matches).
11. Same input, multiple calls → same result (deterministic).

---

## 5. Not in Scope

- Fuzzy/AI seniority inference (permanent non-goal, D-002).
- Seniority hierarchy validation (e.g. blocking "Junior CEO") — curators correct.
- Pay-grade or compensation inference from seniority.
- Multi-level assignments (a role maps to exactly one level).
