# Backend Database Inventory — PRISM

**Engine:** PostgreSQL 17.6 (Supabase) · **Migrations:** Alembic `0001`–`0010` (frozen) · **Tables:** 17 domain + `alembic_version`.
**Verified against live schema:** 17/17 tables, 20 foreign keys, 49 indexes, `alembic_version = 0010`.

Conventions: every table has an integer surrogate PK (`*_id`, `SERIAL`) named `pk_<table>`; timestamps are `TIMESTAMP WITH TIME ZONE` defaulting to `now()`; FK names are `fk_<table>_<target>`; unique constraints `uq_*`; indexes `idx_*` (and `uq_*` for partial-unique indexes). `updated_at` (where present) is bumped by the ORM `onupdate`, not a DB trigger.

---

## Entity-relationship overview

```
capture_source ──< alumni >── study_program
capture_source ──< career_record >── alumni
capture_source ──< company_alias >── company ──> industry
capture_source ──< import_batch                company ──> location
company ──< career_record >── refresh_snapshot
role ──< role_permission >── permission
role ──< app_user
app_user ──< audit_log            (changed_by, nullable)
import_batch ──< staging_row ──< dedup_candidate >── alumni
app_user ──< dedup_candidate      (resolved_by, nullable)
```

---

## Reference / taxonomy tables — migration `0002`

### `study_program`
- **Purpose:** Approved FTMM study programs (+ non-valid ones retained for rejection). D-003/D-004.
- **Columns:** `program_id` PK · `program_name` VARCHAR(200) NOT NULL · `degree_level` VARCHAR(50) NOT NULL · `is_ftmm_valid` BOOL NOT NULL DEFAULT false · `created_at` TIMESTAMPTZ NOT NULL DEFAULT now().
- **PK:** `pk_study_program(program_id)` · **FK:** none · **Unique:** `uq_study_program_name(program_name)` · **Indexes:** PK + unique.
- **Relationships:** referenced by `alumni.study_program_id`.

### `industry`
- **Purpose:** Industry taxonomy — granular `industry_name` + parent `sector_name` (D-042).
- **Columns:** `industry_id` PK · `industry_name` VARCHAR(200) NOT NULL · `sector_name` VARCHAR(200) NOT NULL · `taxonomy_code` VARCHAR(50) NULL · `created_at`.
- **PK:** `pk_industry` · **FK:** none · **Unique:** `uq_industry_name(industry_name)`.
- **Relationships:** referenced by `company.industry_id`.

### `location`
- **Purpose:** Geographic normalization hierarchy (D-019). All but `country` nullable (partial resolution).
- **Columns:** `location_id` PK · `country` VARCHAR(100) NOT NULL · `province`/`city`/`region` VARCHAR(100) NULL · `created_at`.
- **PK:** `pk_location` · **FK:** none · **Unique:** none *(no natural key — audit note O-2)*.
- **Relationships:** referenced by `company.location_id`.

### `capture_source`
- **Purpose:** Data provenance/ingestion source + static curator trust tier (D-049).
- **Columns:** `source_id` PK · `source_type` VARCHAR(100) NOT NULL · `trust_tier` INT NOT NULL · `created_at`.
- **PK:** `pk_capture_source` · **FK:** none · **Unique:** `uq_capture_source_type(source_type)`.
- **Relationships:** referenced by `alumni.source_id`, `career_record.source_id`, `company_alias.source_id`, `import_batch.source_id`.

---

## Snapshot — migration `0003`

### `refresh_snapshot`
- **Purpose:** Per-quarter refresh metadata; career records are tagged with a snapshot for point-in-time reporting (D-021).
- **Columns:** `snapshot_id` PK · `quarter_label` VARCHAR(20) NOT NULL · `refresh_date` DATE NOT NULL · `notes` TEXT NULL · `created_at`.
- **PK:** `pk_refresh_snapshot` · **FK:** none · **Unique:** `uq_refresh_snapshot_quarter_label(quarter_label)`.
- **Relationships:** referenced by `career_record.snapshot_id` (SET NULL).

---

## RBAC / security — migration `0004`

### `role`
- **Purpose:** Application roles (D-026): Admin, Data Curator, Faculty Viewer, Read Only.
- **Columns:** `role_id` PK · `role_name` VARCHAR(50) NOT NULL · `created_at`.
- **PK:** `pk_role` · **Unique:** `uq_role_name`.
- **Relationships:** referenced by `role_permission.role_id`, `app_user.role_id`.

### `permission`
- **Purpose:** Granular permission names (D-026/D-036), assigned to roles.
- **Columns:** `permission_id` PK · `permission_name` VARCHAR(100) NOT NULL · `description` TEXT NULL · `created_at`.
- **PK:** `pk_permission` · **Unique:** `uq_permission_name`.
- **Relationships:** referenced by `role_permission.permission_id`.

### `role_permission`
- **Purpose:** Many-to-many Role ↔ Permission (D-026).
- **Columns:** `id` PK · `role_id` INT NOT NULL · `permission_id` INT NOT NULL.
- **PK:** `pk_role_permission(id)` · **FK:** `fk_role_permission_role → role` (CASCADE), `fk_role_permission_permission → permission` (CASCADE) · **Unique:** `uq_role_permission(role_id, permission_id)`.

### `app_user`
- **Purpose:** Application user keyed by Supabase Auth UUID — the authz store (D-043).
- **Columns:** `user_id` PK · `supabase_uuid` UUID NOT NULL · `role_id` INT NOT NULL · `email` VARCHAR(320) NULL · `is_active` BOOL NOT NULL DEFAULT true · `created_at` · `updated_at` (ORM `onupdate`).
- **PK:** `pk_app_user` · **FK:** `fk_app_user_role → role` (RESTRICT) · **Unique:** `uq_app_user_supabase_uuid(supabase_uuid)`.
- **Relationships:** referenced (nullable) by `audit_log.changed_by`, `import_batch.created_by`, `dedup_candidate.resolved_by`.

---

## Company normalization — migration `0005`

### `company`
- **Purpose:** One canonical record per employer (D-017). `industry_id`/`location_id` assigned by curators later (nullable).
- **Columns:** `company_id` PK · `canonical_name` VARCHAR(300) NOT NULL · `industry_id` INT NULL · `location_id` INT NULL · `created_at`.
- **PK:** `pk_company` · **FK:** `fk_company_industry → industry` (SET NULL), `fk_company_location → location` (SET NULL) · **Unique:** `uq_company_canonical_name`.
- **Indexes:** `idx_company_industry`, `idx_company_location` *(created in 0008)*.
- **Relationships:** referenced by `company_alias.company_id`, `career_record.company_id`.

### `company_alias`
- **Purpose:** Maps each raw employer string → its canonical company (D-017).
- **Columns:** `alias_id` PK · `company_id` INT NOT NULL · `alias_name` VARCHAR(300) NOT NULL · `source_id` INT NULL · `created_at`.
- **PK:** `pk_company_alias` · **FK:** `fk_company_alias_company → company` (CASCADE), `fk_company_alias_source → capture_source` (SET NULL) · **Unique:** `uq_company_alias_name(alias_name)`.
- **Note:** `company_id` FK is **not** indexed (audit L1).

---

## Alumni — migration `0006` (+ `validationstatus` enum)

### `alumni`
- **Purpose:** Core alumni record (D-023/D-040/D-044/D-046/D-047).
- **Columns:** `alumni_id` PK · `public_id` UUID NOT NULL DEFAULT `gen_random_uuid()` · `full_name` VARCHAR(300) NOT NULL · `university` VARCHAR(200) NOT NULL DEFAULT 'Universitas Airlangga' · `study_program_id` INT NOT NULL · `graduation_year` INT NOT NULL · `linkedin_url` VARCHAR(500) NULL · `validation_status` `validationstatus` ENUM('pending','validated','rejected') NOT NULL DEFAULT 'pending' · `source_id` INT NOT NULL · `created_at` · `updated_at`.
- **PK:** `pk_alumni` · **FK:** `fk_alumni_study_program → study_program` (RESTRICT), `fk_alumni_source → capture_source` (RESTRICT) · **Unique:** `uq_alumni_public_id`.
- **Indexes:** **partial-unique** `uq_alumni_linkedin_url` `WHERE linkedin_url IS NOT NULL` (D-044); filter indexes `idx_alumni_graduation_year`, `idx_alumni_study_program`, `idx_alumni_validation_status` *(created in 0008)*.
- **Relationships:** referenced by `career_record.alumni_id` (CASCADE), `dedup_candidate.matched_alumni_id` (CASCADE).

---

## Audit — migration `0007`

### `audit_log`
- **Purpose:** Immutable record of every mutation routed through the gateway (D-025).
- **Columns:** `audit_id` PK · `table_name` VARCHAR(100) NOT NULL · `record_id` VARCHAR(100) NOT NULL · `action_type` VARCHAR(20) NOT NULL · `old_values` JSONB NULL · `new_values` JSONB NULL · `changed_by` INT NULL · `changed_at` TIMESTAMPTZ NOT NULL DEFAULT now().
- **PK:** `pk_audit_log` · **FK:** `fk_audit_log_changed_by → app_user` (SET NULL) · **Unique:** none.
- **Note:** `changed_by` FK is **not** indexed (audit L1).

---

## Career records + filter indexes — migration `0008`

### `career_record`
- **Purpose:** Per-alumnus career entry; exactly one `is_current` per alumnus (D-020/D-029). Provenance required (D-041).
- **Columns:** `career_record_id` PK · `alumni_id` INT NOT NULL · `company_id` INT NOT NULL · `role_title` VARCHAR(300) NOT NULL · `seniority` VARCHAR(100) NULL · `is_current` BOOL NOT NULL DEFAULT false · `snapshot_id` INT NULL · `source_id` INT NOT NULL · `captured_on` DATE NULL · `created_at`.
- **PK:** `pk_career_record` · **FK:** `fk_career_record_alumni → alumni` (CASCADE), `fk_career_record_company → company` (RESTRICT), `fk_career_record_snapshot → refresh_snapshot` (SET NULL), `fk_career_record_source → capture_source` (RESTRICT).
- **Indexes:** **partial-unique** `uq_career_one_current_per_alumni(alumni_id)` `WHERE is_current = true` (D-020); `idx_career_company`, `idx_career_snapshot`, `idx_career_is_current`, `idx_career_alumni`.
- **Note:** `source_id` FK not indexed (audit L1). *This migration also creates the `alumni` and `company` filter indexes listed above.*

---

## Import staging — migration `0009`

### `import_batch`
- **Purpose:** One row per import run; tracks source, filename, counts, status, actor.
- **Columns:** `batch_id` PK · `source_id` INT NOT NULL · `filename` VARCHAR(500) NOT NULL · `total_rows`/`parsed_rows`/`error_rows` INT NOT NULL · `status` VARCHAR(20) NOT NULL DEFAULT 'pending' · `created_by` INT NULL · `created_at`.
- **PK:** `pk_import_batch` · **FK:** `fk_import_batch_source → capture_source` (RESTRICT), `fk_import_batch_created_by → app_user` (SET NULL) · **Unique:** none.
- **Indexes:** `idx_import_batch_source`, `idx_import_batch_created_by`, `idx_import_batch_status`.
- **Relationships:** referenced by `staging_row.batch_id` (CASCADE).

### `staging_row`
- **Purpose:** One row per source-file body row; raw cells + the A1 candidate shape; landing zone before normalization.
- **Columns:** `staging_row_id` PK · `batch_id` INT NOT NULL · `row_number` INT NOT NULL · `raw_full_name`/`raw_study_program`/`raw_employer`/`raw_role_title`/`raw_location` VARCHAR(500) NULL · `raw_graduation_year` INT NULL · `raw_linkedin_url` VARCHAR(1000) NULL · `raw_extra` JSONB NULL · `row_status` VARCHAR(20) NOT NULL DEFAULT 'pending' · `row_error` TEXT NULL · `created_at`.
- **PK:** `pk_staging_row` · **FK:** `fk_staging_row_batch → import_batch` (CASCADE) · **Unique:** none.
- **Indexes:** `idx_staging_row_batch`, `idx_staging_row_status`.
- **Relationships:** referenced by `dedup_candidate.staging_row_id` (CASCADE).

---

## Dedup queue — migration `0010`

### `dedup_candidate`
- **Purpose:** Curator review queue for Tier-2 matches (name+program+year) before commit (D-045). No auto-merge.
- **Columns:** `dedup_candidate_id` PK · `staging_row_id` INT NOT NULL · `matched_alumni_id` INT NOT NULL · `resolution` VARCHAR(20) NOT NULL DEFAULT 'pending' ('pending' | 'merge' | 'keep_separate') · `resolved_by` INT NULL · `resolved_at` TIMESTAMPTZ NULL · `created_at`.
- **PK:** `pk_dedup_candidate` · **FK:** `fk_dedup_candidate_staging_row → staging_row` (CASCADE), `fk_dedup_candidate_matched_alumni → alumni` (CASCADE), `fk_dedup_candidate_resolved_by → app_user` (SET NULL) · **Unique:** none.
- **Indexes:** `idx_dedup_candidate_staging_row`, `idx_dedup_candidate_matched_alumni`, `idx_dedup_candidate_resolved_by`, `idx_dedup_candidate_resolution`.

---

## Migration map

| Migration | Creates |
|-----------|---------|
| `0001_baseline` | (no-op baseline) |
| `0002_reference_tables` | `study_program`, `industry`, `location`, `capture_source` |
| `0003_refresh_snapshot` | `refresh_snapshot` |
| `0004_security_tables` | `role`, `permission`, `role_permission`, `app_user` |
| `0005_company` | `company`, `company_alias` |
| `0006_alumni` | `alumni` + `validationstatus` enum + partial-unique `uq_alumni_linkedin_url` |
| `0007_audit_log` | `audit_log` |
| `0008_career_record_indexes_constraints` | `career_record` + partial-unique `uq_career_one_current_per_alumni` + alumni/career/company filter indexes |
| `0009_staging_tables` | `import_batch`, `staging_row` |
| `0010_dedup_candidate` | `dedup_candidate` |

## Known database notes (from production audit)

- **M1:** models don't declare the migration-created indexes and `Base` has no `naming_convention` → `alembic revision --autogenerate` would try to drop them (resolve forward, do not edit frozen migrations).
- **L1:** unindexed FK columns on growth tables (`company_alias.company_id`, `audit_log.changed_by`, `alumni.source_id`, `career_record.source_id`).
- **O-2:** `location` has no natural unique key (duplicate locations possible).
