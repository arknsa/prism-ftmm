# IMPORT_FILE_FORMAT_SPEC.md — Artifact A1

> **Status:** Approved  
> **Required by:** Phase 3, Session S1 (P3.2 import parser)  
> **Resolves:** Q-010 (import trigger surface / file format — build-time detail)  
> **Sources covered:** LinkedIn, Verified Faculty Record, Tracer Study (D-005)  
> **Last updated:** 2026-07-01

---

## General rules (all sources)

- **Formats accepted:** CSV (`.csv`) and XLSX (`.xlsx`).
- **Encoding:** UTF-8.
- **Header row:** required; first row is the header. Body rows start at row 2.
- **Column matching:** case-insensitive; leading/trailing whitespace in header names is stripped.
- **Extra columns:** any column not listed below is captured verbatim in `raw_extra` (JSONB) and ignored by the pipeline.
- **Malformed rows:** a row missing a required column value (empty or whitespace-only) is recorded with `row_status = "error"` and an error message — **never silently dropped** (D-047 cursor principle).
- **Absent employer:** if `employer` is absent or blank, an alumni staging record is still written (with no career candidate); the career-candidate fields (`employer`, `role_title`, `location`) are stored as NULL on the staging row.
- **Row ordering:** the parser preserves file row order; row numbers are 1-indexed (header = 1, first body row = 2).

---

## Source: LinkedIn (`source_type = "LinkedIn"`)

### Required columns

| Column name | Type | Notes |
|-------------|------|-------|
| `full_name` | text | Alumnus full name |
| `study_program` | text | Raw program string — matched against 5 canonical programs in S5 |
| `graduation_year` | integer | 4-digit year, e.g. `2022` |
| `employer` | text | Raw employer / company name |
| `role_title` | text | Job title |
| `location` | text | Raw location string (city, country, or both) |

### Optional columns

| Column name | Type | Notes |
|-------------|------|-------|
| `linkedin_url` | text | LinkedIn profile URL; nullable + partial-unique (D-044) |
| `notes` | text | Free text; stored in `raw_extra`, ignored by pipeline |

---

## Source: Verified Faculty Record (`source_type = "Verified Faculty Record"`)

Higher trust-tier source (trust_tier = 1). Employment data may be absent for recent graduates.

### Required columns

| Column name | Type | Notes |
|-------------|------|-------|
| `full_name` | text | Alumnus full name |
| `study_program` | text | Raw program string |
| `graduation_year` | integer | 4-digit year |

### Optional columns

| Column name | Type | Notes |
|-------------|------|-------|
| `employer` | text | Raw employer name (may be absent) |
| `role_title` | text | Job title |
| `location` | text | Raw location string |
| `linkedin_url` | text | LinkedIn profile URL |
| `notes` | text | Free text; stored in `raw_extra` |

---

## Source: Tracer Study (`source_type = "Tracer Study"`)

Survey-based data; employment status may be included as a raw text field.

### Required columns

| Column name | Type | Notes |
|-------------|------|-------|
| `full_name` | text | Alumnus full name |
| `study_program` | text | Raw program string |
| `graduation_year` | integer | 4-digit year |

### Optional columns

| Column name | Type | Notes |
|-------------|------|-------|
| `employer` | text | Raw employer name |
| `role_title` | text | Job title |
| `location` | text | Raw location string |
| `linkedin_url` | text | LinkedIn profile URL |
| `employed_status` | text | Raw survey value (e.g. `"Employed"`, `"Student"`); stored in `raw_extra` only — employment semantics are derived from presence of a career record (D-048), not from this field |
| `notes` | text | Free text; stored in `raw_extra` |

---

## Staging row mapping summary

After parsing, every body row is written to `staging_row` with:

| Staging field | Source column |
|---------------|---------------|
| `raw_full_name` | `full_name` |
| `raw_study_program` | `study_program` |
| `raw_graduation_year` | `graduation_year` (integer) |
| `raw_employer` | `employer` (NULL if absent) |
| `raw_role_title` | `role_title` (NULL if absent) |
| `raw_location` | `location` (NULL if absent) |
| `raw_linkedin_url` | `linkedin_url` (NULL if absent) |
| `raw_extra` | all remaining columns as `{column: value}` JSONB |
| `row_number` | 1-indexed position in file (header = 1) |
| `row_status` | `"pending"` (parseable) or `"error"` (missing required field) |
| `row_error` | error message string if `row_status = "error"`, else NULL |
