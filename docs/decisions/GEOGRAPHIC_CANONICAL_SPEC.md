# GEOGRAPHIC_CANONICAL_SPEC.md — Artifact A3

> **Status:** Approved  
> **Required by:** Phase 3, Session S3 (P3.8 location normalization)  
> **Resolves:** Q-009 (geographic normalization approach — build-time detail)  
> **Decision basis:** D-019 (LOCATION table: country/province/city/region), seed_location.py (Phase 1 seed), D-039 (deterministic processing).  
> **Last updated:** 2026-07-01

---

## 1. Design Constraints

- **Deterministic only** (D-039, D-002). No fuzzy matching, no geocoding API, no inference.
- **LOCATION table** already seeded with Indonesian provinces/cities + sentinel rows (Phase 1 `seed_location.py`).
- `country` is **required** on every LOCATION row. `province`, `city`, `region` are nullable (partial resolution is acceptable).
- `resolve_location` returns a `LOCATION` row or `None` (when resolution is impossible per rules below).
- **First-sight creation:** if a raw location string does not match any existing LOCATION row, a new LOCATION row is created (with best-effort partial fields) so no data is silently dropped.

---

## 2. Input Format

Raw location strings from source files are free-form text, typically one of:
- `"Jakarta Indonesia"` — city + country
- `"Surabaya, East Java, Indonesia"` — city + province + country
- `"Jakarta"` — city only
- `"Indonesia"` — country only
- `"Remote"` / `"Work from Home"` / `"WFH"` — remote work indicator
- `""` (empty/blank) — absent location data

---

## 3. Normalization Algorithm (deterministic)

### Step 1 — Blank/absent
If the raw location string is blank or whitespace-only:  
→ Return `None`. No LOCATION row is created; `raw_location` on the staging row is already NULL.

### Step 2 — Remote sentinel matching
If the lowercased raw string contains any of: `"remote"`, `"wfh"`, `"work from home"`, `"work-from-home"`:  
→ Look up LOCATION where `country = 'Remote'`. Return it.  
(Seeded as: `country="Remote", province=None, city=None, region="Remote"`.)

### Step 3 — Tokenize the raw string
Split the raw string by `,` and/or whitespace, strip each token. Normalize tokens to title-case for matching.

Apply the following priority order:

#### 3a — Known country extraction
Detect a country token by matching against a known country list (see §5).  
If found: extract it as `country_token`; remaining tokens are candidate city/province.

If no country token found: default `country_token = "Indonesia"` (FTMM alumni are overwhelmingly Indonesian).

#### 3b — Known city/province matching
Match remaining tokens against LOCATION rows in the DB:
1. Exact `city` match → use that row's `(country, province, city)`.
2. Exact `province` match → use `(country, province, city=None)` if a province-level row exists; else create one.
3. No match → create a new LOCATION row with `country=country_token`, `province=None`, `city=None`.

#### 3c — First-sight creation
If no existing LOCATION row matches: create a new row with the best-effort fields extracted. Set `region=None`. The curator can correct/merge later.

### Step 4 — Return
Return the LOCATION row (existing or newly created).

---

## 4. Sentinel Rows

| Use case | country | province | city | region |
|----------|---------|----------|------|--------|
| Remote worker | `Remote` | NULL | NULL | `Remote` |
| International / non-Indonesia | `Other` | NULL | NULL | `International` |
| Blank/absent location | — | — | — | — (returns `None`) |

---

## 5. Known Country List (seed set)

These country name strings (and common variants) are recognized during token matching:

| Canonical country | Recognized tokens (case-insensitive) |
|-------------------|--------------------------------------|
| `Indonesia` | `indonesia`, `id` |
| `Singapore` | `singapore`, `sg` |
| `Malaysia` | `malaysia`, `my` |
| `United States` | `united states`, `usa`, `us`, `america` |
| `United Kingdom` | `united kingdom`, `uk`, `england` |
| `Australia` | `australia`, `au` |
| `Japan` | `japan`, `jp` |
| `South Korea` | `south korea`, `korea`, `kr` |
| `Netherlands` | `netherlands`, `holland`, `nl` |
| `Germany` | `germany`, `de` |
| `Other` | (everything else not matched above) |

Any country string that is not in this list results in `country = raw_country_token` (stored as-is) with a new LOCATION row created.

---

## 6. Normalization Invariants (testable)

1. Blank/absent input → `None` returned (no row created).
2. `"Remote"` → returns the seeded Remote sentinel row.
3. Same raw string input on multiple calls → returns the same LOCATION row (deterministic, idempotent).
4. First-sight: a new raw string creates exactly one LOCATION row and returns it.
5. Known city string ("Jakarta", "Surabaya") → returns the matching seeded LOCATION row (no duplicate created).
6. Country defaulting: raw string with no country token → `country = "Indonesia"`.

---

## 7. Not in Scope

- Fuzzy matching or geocoding API calls (permanent non-goal, D-002).
- Province/city hierarchy validation (partial resolution is accepted).
- Retroactive correction of existing LOCATION rows (curator's task via Phase 4).
- Region field population (remains NULL for non-sentinel rows; curator assigns if needed).
