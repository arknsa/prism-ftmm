# PROGRAM_VARIANT_MAP_SPEC.md — Artifact A6

> **Status:** Approved  
> **Required by:** Phase 3 Session S5 (P3.4 — program/university matcher)  
> **Resolves:** Q-005 (program-name variant → canonical mapping — build-time detail)  
> **Decision basis:** D-003, D-004 (five approved FTMM programs), D-024 (validation via curator), D-040 (university stored as attribute), D-047 (validation_status: pending/validated/rejected), D-039 (deterministic).  
> **Date:** 2026-07-01

---

## 1. Design Constraints

- **Deterministic only** (D-039, D-002). No fuzzy matching, no Levenshtein, no ML.
- The five canonical program names are fixed per D-004 and match `seed_study_programs.py` exactly.
- Matching is case-insensitive and whitespace-normalized (strip + collapse).
- Anything not explicitly in the variant map → routes to `"Other / Unknown"` sentinel (`is_ftmm_valid=False`).
- Final `validated` transition requires **curator gate** (D-024) — the matcher only sets eligibility.
- University matching: explicit string check only (D-040).

---

## 2. Canonical Program Names (from seed_study_programs.py, D-004)

| Canonical Name | `is_ftmm_valid` |
|----------------|-----------------|
| `Technology of Data Science` | True |
| `Industrial Engineering` | True |
| `Electrical Engineering` | True |
| `Nanotechnology Engineering` | True |
| `Robotics and Artificial Intelligence Engineering` | True |
| `Other / Unknown` | False (sentinel) |

---

## 3. Program Variant Map

The following raw strings (normalized to lowercase, whitespace-collapsed) map to the canonical program. The match is **exact after normalization** — no substring or partial matching.

### Technology of Data Science
| Raw variant (normalized, case-insensitive) |
|--------------------------------------------|
| `technology of data science` |
| `teknologi sains data` |
| `data science` |
| `data science technology` |
| `tech data science` |
| `tsd` |
| `data science tech` |
| `sains data teknologi` |
| `teknik data` |

### Industrial Engineering
| Raw variant (normalized, case-insensitive) |
|--------------------------------------------|
| `industrial engineering` |
| `teknik industri` |
| `industrial eng` |
| `ie` |
| `ti` |
| `industri` |
| `industrial` |
| `teknik industri (s1)` |

### Electrical Engineering
| Raw variant (normalized, case-insensitive) |
|--------------------------------------------|
| `electrical engineering` |
| `teknik elektro` |
| `electrical eng` |
| `ee` |
| `te` |
| `elektro` |
| `teknik ketenagalistrikan` |
| `electrical` |

### Nanotechnology Engineering
| Raw variant (normalized, case-insensitive) |
|--------------------------------------------|
| `nanotechnology engineering` |
| `teknik nanoteknologi` |
| `nanotechnology eng` |
| `nano` |
| `nanoteknologi` |
| `teknik nano` |
| `nte` |
| `nanotechnology` |

### Robotics and Artificial Intelligence Engineering
| Raw variant (normalized, case-insensitive) |
|--------------------------------------------|
| `robotics and artificial intelligence engineering` |
| `teknik robotika dan kecerdasan buatan` |
| `robotics ai` |
| `robotics & ai` |
| `robotics and ai engineering` |
| `rai` |
| `robotika` |
| `kecerdasan buatan` |
| `robotics` |
| `ai engineering` |
| `trkb` |
| `teknik robot` |
| `robotics engineering` |

---

## 4. University Matching

University validity is checked separately from program matching. The rule is explicit string match (D-040):

| Canonical | Recognized variants (case-insensitive, whitespace-normalized) |
|-----------|--------------------------------------------------------------|
| `Universitas Airlangga` | `universitas airlangga`, `unair`, `ua`, `airlangga university`, `airlangga` |

Any other university string → `is_unair = False`. The alumni are still processed; they may be `pending` or `rejected` depending on validation-status rules.

---

## 5. Validation Status Assignment Rules (D-047)

The program matcher and university checker together produce a `validation_status` candidate:

| Program match | University match | Result |
|--------------|-----------------|--------|
| `is_ftmm_valid = True` | `is_unair = True` | → `pending` (curator must set `validated`; never auto-validated) |
| `is_ftmm_valid = True` | `is_unair = False` | → `pending` (curator reviews — may be transfer/exchange student) |
| `is_ftmm_valid = False` (sentinel) | `is_unair = True` | → `pending` (UNAIR student, unknown program — curator classifies) |
| `is_ftmm_valid = False` (sentinel) | `is_unair = False` | → `rejected` (neither program nor university matches; retained for audit/anti-churn per D-047) |

**Key constraint (D-047, D-024):** Only `validated` alumni appear in analytics. The pipeline sets `pending` or `rejected`. The **curator** explicitly transitions `pending → validated` or `pending → rejected` through the Phase 4 curator UI (P4.8). The pipeline never auto-validates.

---

## 6. Algorithm (deterministic)

```
normalize(s) = lowercase(collapse_whitespace(strip(s)))

match_program(raw_program: str | None) -> StudyProgram:
    if raw_program is None or normalize(raw_program) == "":
        return SENTINEL  # "Other / Unknown"
    key = normalize(raw_program)
    return VARIANT_MAP.get(key, SENTINEL)

is_unair(raw_university: str | None) -> bool:
    if raw_university is None:
        return False
    key = normalize(raw_university)
    return key in UNAIR_VARIANTS
```

---

## 7. Testable Invariants

1. `None` / blank program → `"Other / Unknown"` sentinel.
2. `"Teknik Industri"` → `Industrial Engineering` (`is_ftmm_valid=True`).
3. `"DATA SCIENCE"` → `Technology of Data Science` (case-insensitive).
4. `"Philosophy"` → `"Other / Unknown"` (`is_ftmm_valid=False`).
5. `"UNAIR"` → `is_unair=True`.
6. `"MIT"` → `is_unair=False`.
7. Valid program + UNAIR → `validation_status = "pending"` (not `"validated"`).
8. Sentinel + non-UNAIR → `validation_status = "rejected"`.
9. Same input → same output (deterministic, idempotent).
10. Every variant in the map maps to a program with `is_ftmm_valid=True` or the sentinel.

---

## 8. Not in Scope

- Fuzzy/AI program matching (permanent non-goal, D-002).
- Auto-validation (curator must always confirm `validated` transition, D-024).
- Program hierarchy or grouping by faculty — only the five programs exist in scope (D-004).
- Adding new variants at runtime — map is code-level constants; operator adds variants by code change + review.
