# PHASE1_EXECUTION_PLAN.md

> **Binding inputs:** `docs/CLAUDE_CODE_HANDOFF.md`, `docs/decisions/DECISIONS.md`, `docs/architecture/IMPLEMENTATION_ROADMAP.md`.
> **Phase 1 goal:** the full approved schema (Schema v1 + D-040–D-051 deltas) live in Supabase, with seed/reference data and the audit-service contract.
> **Phase 1 exit criterion:** `alembic upgrade head` builds the complete schema on Supabase; seed scripts populate all reference data; audit contract module is in place.
>
> **Pre-conditions (operator must complete before implementation begins):**
> - P0.8 complete: Supabase project created; `DATABASE_URL` (pooler) + `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` + `SUPABASE_JWT_SECRET` captured and set in backend `.env`.
> - `alembic upgrade head` against Supabase runs `0001_baseline` without error.
>
> **Out of scope for Phase 1 (never implement):** Auth/JWT, RBAC enforcement, import pipelines, aggregation queries, dashboard pages, AI/ML/fuzzy matching, real-time, caching, microservices.

---

## Task Order (approved execution sequence)

```
P1.1 (reference tables)
  └─> P1.2 (COMPANY + COMPANY_ALIAS)
  └─> P1.3 (ALUMNI)
       └─> P1.4 (CAREER_RECORD)  ← also needs P1.2
            └─> P1.8 (indexes)
            └─> P1.9 (constraints)
P0.5 (already done) ─> P1.5 (REFRESH_SNAPSHOT)   ← independent; start of P1
P0.5 (already done) ─> P1.6 (security tables)
  └─> P1.7 (AUDIT_LOG)
P1.1 ─> P1.10 (seed STUDY_PROGRAM)
P1.1 ─> P1.11 (seed CAPTURE_SOURCE)
P1.6 ─> P1.12 (seed ROLE/PERMISSION/ROLE_PERMISSION)
P1.1 ─> P1.13 (seed INDUSTRY + LOCATION)
P1.7 ─> P1.14 (audit-write service contract)
```

**Parallelizable within a session:**
- After P1.1 is merged: P1.2 and P1.3 can be written in parallel (different tables; P1.4 waits for both).
- P1.5 and P1.6 are independent of P1.1–P1.4 and can be done in the same session.
- P1.10, P1.11, P1.13 can be written together once P1.1 migration is applied (all seed reference tables that exist after P1.1).
- P1.8 and P1.9 can be delivered in the same migration as P1.4 (they are addenda to the same migration file).

---

## Implementation Sessions (grouping for solo dev)

| Session | Tasks | Rationale |
|---------|-------|-----------|
| **S1 — Reference + Security foundation** | P1.1, P1.5, P1.6 | Independent of each other; creates all parent tables that everything else FKs into. Apply migration and verify on Supabase before S2. |
| **S2 — Core entity schema** | P1.2, P1.3, P1.4, P1.7, P1.8, P1.9 | All depend on S1 tables. P1.4 bundles indexes (P1.8) and constraints (P1.9) in one migration file. P1.7 depends on P1.6 (AUDIT_LOG FK to APP_USER). |
| **S3 — Seed data** | P1.10, P1.11, P1.12, P1.13 | All seeds require the schema from S1–S2 to be applied. Can be written in parallel, loaded sequentially. |
| **S4 — Audit service contract** | P1.14 | Depends on P1.7 (AUDIT_LOG table exists). Pure Python; no migration. |

---

## Task Details

---

### P1.1 — Reference tables migration
**Session:** S1
**Complexity:** M

**Objective:**
Create Alembic migration and SQLAlchemy models for the four reference/taxonomy tables: `STUDY_PROGRAM`, `INDUSTRY`, `LOCATION`, `CAPTURE_SOURCE`. These are parent tables with no FKs to other Phase 1 tables; everything else depends on them.

**Decisions covered:** D-003, D-004 (`is_ftmm_valid`), D-009, D-010, D-018, D-019, D-042 (`industry_name` + `sector_name`), D-049 (static trust tier on CAPTURE_SOURCE).

**Files to create:**
- `backend/fastapi-app/app/models/__init__.py` — re-exports all models
- `backend/fastapi-app/app/models/reference.py` — `StudyProgram`, `Industry`, `Location`, `CaptureSource` SQLAlchemy mapped classes
- `backend/fastapi-app/migrations/versions/0002_reference_tables.py` — Alembic migration

**Files to modify:**
- `backend/fastapi-app/migrations/env.py` — ensure `Base.metadata` imports from `app.models` (currently imports from `app.db`; extend or move the import so all model modules are loaded before `target_metadata` is set)

**Model specification:**

```
StudyProgram
  program_id        Integer PK autoincrement
  program_name      String(200) NOT NULL UNIQUE
  degree_level      String(50)  NOT NULL            -- e.g. "S1", "D4"
  is_ftmm_valid     Boolean     NOT NULL DEFAULT false
  created_at        DateTime    NOT NULL DEFAULT now()

Industry
  industry_id       Integer PK autoincrement
  industry_name     String(200) NOT NULL UNIQUE     -- granular (D-042)
  sector_name       String(200) NOT NULL            -- parent grouping (D-042)
  taxonomy_code     String(50)  NULLABLE            -- optional external code
  created_at        DateTime    NOT NULL DEFAULT now()

Location
  location_id       Integer PK autoincrement
  country           String(100) NOT NULL
  province          String(100) NULLABLE
  city              String(100) NULLABLE
  region            String(100) NULLABLE            -- e.g. "Southeast Asia"
  created_at        DateTime    NOT NULL DEFAULT now()

CaptureSource
  source_id         Integer PK autoincrement
  source_type       String(100) NOT NULL UNIQUE     -- "LinkedIn" | "Verified Faculty Record" | "Tracer Study" | "Alumni Form"
  trust_tier        Integer     NOT NULL            -- 1=Verified, 2=Tracer, 3=LinkedIn (lower = higher trust, D-049)
  created_at        DateTime    NOT NULL DEFAULT now()
```

Notes on `CaptureSource`:
- Field was `confidence_level` in Schema v1; D-049 redefines it as a **static trust tier** integer (never computed, curator-assigned at seed time). Name the column `trust_tier` (D-049 endorses optional rename from `confidence_level`).
- `trust_tier` is enforced at seed time; no constraint beyond NOT NULL needed.

**Dependencies:** P0.5 (Alembic wired, `Base` importable, empty baseline applied).

**Acceptance criteria:**
1. `alembic upgrade head` applies migration 0002 without error on a fresh Supabase schema.
2. `alembic downgrade -1` reverts cleanly.
3. All four tables present in Supabase with correct columns and types.
4. `mypy app` passes. `ruff check app` passes.
5. No hardcoded data in the migration (seeds come in P1.10–P1.13).

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run mypy app
uv run ruff check app
uv run black --check app
```

---

### P1.5 — REFRESH_SNAPSHOT migration
**Session:** S1
**Complexity:** S

**Objective:**
Create the `REFRESH_SNAPSHOT` table which stores per-quarter metadata. Independent of other Phase 1 tables (no FK dependencies from this table itself); `CAREER_RECORD` will FK into it in P1.4.

**Decisions covered:** D-006, D-007, D-021.

**Files to create:**
- `backend/fastapi-app/app/models/snapshot.py` — `RefreshSnapshot` mapped class
- `backend/fastapi-app/migrations/versions/0003_refresh_snapshot.py`

**Model specification:**

```
RefreshSnapshot
  snapshot_id     Integer   PK autoincrement
  quarter_label   String(20) NOT NULL UNIQUE   -- e.g. "2025-Q1"
  refresh_date    Date       NOT NULL
  notes           Text       NULLABLE
  created_at      DateTime   NOT NULL DEFAULT now()
```

**Dependencies:** P0.5.

**Acceptance criteria:**
1. Migration 0003 applies and reverts cleanly.
2. `quarter_label` has a UNIQUE constraint.
3. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run mypy app
uv run ruff check app
```

---

### P1.6 — Security tables migration
**Session:** S1
**Complexity:** M

**Objective:**
Create the RBAC security tables: `APP_USER`, `ROLE`, `PERMISSION`, `ROLE_PERMISSION`. `APP_USER` is keyed by the Supabase user UUID (D-043). No auth enforcement yet — that is Phase 2.

**Decisions covered:** D-026, D-032, D-036, D-043.

**Files to create:**
- `backend/fastapi-app/app/models/security.py` — `AppUser`, `Role`, `Permission`, `RolePermission` mapped classes
- `backend/fastapi-app/migrations/versions/0004_security_tables.py`

**Model specification:**

```
Role
  role_id     Integer    PK autoincrement
  role_name   String(50) NOT NULL UNIQUE   -- "Admin" | "Data Curator" | "Faculty Viewer" | "Read Only"
  created_at  DateTime   NOT NULL DEFAULT now()

Permission
  permission_id   Integer    PK autoincrement
  permission_name String(100) NOT NULL UNIQUE  -- e.g. "alumni:read", "alumni:validate"
  description     Text        NULLABLE
  created_at      DateTime    NOT NULL DEFAULT now()

RolePermission
  id              Integer PK autoincrement
  role_id         Integer FK → Role.role_id  NOT NULL
  permission_id   Integer FK → Permission.permission_id  NOT NULL
  UNIQUE(role_id, permission_id)

AppUser
  user_id         Integer    PK autoincrement
  supabase_uuid   UUID       NOT NULL UNIQUE   -- Supabase Auth user UUID (the sync point, D-043)
  role_id         Integer    FK → Role.role_id  NOT NULL
  email           String(320) NULLABLE          -- denormalized for admin convenience; source of truth is Supabase Auth
  is_active       Boolean    NOT NULL DEFAULT true
  created_at      DateTime   NOT NULL DEFAULT now()
  updated_at      DateTime   NOT NULL DEFAULT now()
```

Notes:
- `supabase_uuid` column type: use `UUID` (PostgreSQL native UUID type via `sqlalchemy.dialects.postgresql.UUID`).
- `email` is deliberately nullable and informational only — Supabase Auth owns identity; this is a convenience field.
- Do not enforce uniqueness on `email` here (email changes go through Supabase Auth).

**Dependencies:** P0.5.

**Acceptance criteria:**
1. Migration 0004 applies and reverts cleanly.
2. `supabase_uuid` is UNIQUE and NOT NULL.
3. All FK relationships defined.
4. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run mypy app
uv run ruff check app
```

---

### P1.2 — COMPANY + COMPANY_ALIAS migration
**Session:** S2
**Complexity:** M

**Objective:**
Create `COMPANY` (canonical, unique name, FK to Industry and Location) and `COMPANY_ALIAS` (many raw names → one canonical company, with provenance). Redundant `country` column is intentionally excluded per Q-021.

**Decisions covered:** D-008, D-017, D-018, D-019; Q-021 (drop redundant `country`), Q-023 (FK targets declared).

**Files to create:**
- `backend/fastapi-app/app/models/company.py` — `Company`, `CompanyAlias` mapped classes
- `backend/fastapi-app/migrations/versions/0005_company.py`

**Model specification:**

```
Company
  company_id      Integer    PK autoincrement
  canonical_name  String(300) NOT NULL UNIQUE
  industry_id     Integer    FK → Industry.industry_id  NULLABLE   -- nullable: unknown at import time
  location_id     Integer    FK → Location.location_id  NULLABLE   -- nullable: unknown at import time
  created_at      DateTime   NOT NULL DEFAULT now()

CompanyAlias
  alias_id        Integer    PK autoincrement
  company_id      Integer    FK → Company.company_id  NOT NULL
  alias_name      String(300) NOT NULL
  source_id       Integer    FK → CaptureSource.source_id  NULLABLE  -- per Q-023
  created_at      DateTime   NOT NULL DEFAULT now()
  UNIQUE(alias_name)   -- one alias name maps to exactly one canonical company
```

Notes:
- `industry_id` and `location_id` on Company are nullable because a newly discovered company may not have classification yet; curators fill them in (Phase 4, P4.10).
- `CompanyAlias.alias_name` unique constraint ensures a raw string is unambiguously mapped.

**Dependencies:** P1.1 (Industry, Location, CaptureSource tables must exist).

**Acceptance criteria:**
1. Migration 0005 applies and reverts cleanly.
2. `canonical_name` UNIQUE; `alias_name` UNIQUE.
3. FK to `industry_id`, `location_id`, `source_id` declared.
4. No `country` column on `Company` (per Q-021).
5. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run mypy app
uv run ruff check app
```

---

### P1.3 — ALUMNI migration
**Session:** S2
**Complexity:** M

**Objective:**
Create the `ALUMNI` table incorporating all D-040/D-044/D-046/D-047 deltas from the blocker-resolution pass: `public_id` UUID, `university` text default, `linkedin_url` nullable + partial-unique, `validation_status` enum, `source_id` FK for primary provenance.

**Decisions covered:** D-023, D-024, D-040, D-044, D-046, D-047.

**Files to create:**
- `backend/fastapi-app/app/models/alumni.py` — `Alumni` mapped class + `ValidationStatus` Python enum
- `backend/fastapi-app/migrations/versions/0006_alumni.py`

**Model specification:**

```
ValidationStatus (Python enum + PG enum)
  pending | validated | rejected

Alumni
  alumni_id           Integer    PK autoincrement
  public_id           UUID       NOT NULL UNIQUE    -- system identity (D-044)
  full_name           String(300) NOT NULL
  university          String(200) NOT NULL DEFAULT 'Universitas Airlangga'  -- D-040
  study_program_id    Integer    FK → StudyProgram.program_id  NOT NULL
  graduation_year     Integer    NOT NULL
  linkedin_url        String(500) NULLABLE           -- D-044: nullable; partial-unique below
  validation_status   Enum(ValidationStatus) NOT NULL DEFAULT 'pending'     -- D-047
  source_id           Integer    FK → CaptureSource.source_id  NOT NULL     -- D-046
  created_at          DateTime   NOT NULL DEFAULT now()
  updated_at          DateTime   NOT NULL DEFAULT now()
```

Partial-unique index (defined in migration, not on model class):
```sql
CREATE UNIQUE INDEX uq_alumni_linkedin_url
ON alumni (linkedin_url)
WHERE linkedin_url IS NOT NULL;
```

Notes:
- `public_id` default: generate with `gen_random_uuid()` at DB level (PostgreSQL built-in, available on Supabase) OR accept the value from application layer. Prefer DB-side default so it is always set.
- `ValidationStatus` must be a PostgreSQL ENUM type (created with `sa.Enum('pending','validated','rejected', name='validationstatus', create_type=True)`). The migration must create it before the table and drop it on downgrade after the table.
- `updated_at` should be kept current via an application-level hook (SQLAlchemy `onupdate`); no DB trigger in Phase 1 (D-039: simplicity).

**Dependencies:** P1.1 (StudyProgram, CaptureSource).

**Acceptance criteria:**
1. Migration 0006 applies and reverts cleanly (PG enum created/dropped correctly).
2. `public_id` UNIQUE and NOT NULL; `linkedin_url` partial-unique index present.
3. `validation_status` rejects values outside the enum.
4. `university` defaults to `'Universitas Airlangga'`.
5. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
# Verify in Supabase SQL editor:
# SELECT indexname, indexdef FROM pg_indexes WHERE tablename='alumni';
uv run mypy app
uv run ruff check app
```

---

### P1.7 — AUDIT_LOG migration
**Session:** S2
**Complexity:** S

**Objective:**
Create the `AUDIT_LOG` table for recording every mutation that passes through FastAPI (D-025). No writes yet — wired in Phase 4 (P4.6).

**Decisions covered:** D-025, D-036; Q-023 (FK target on `changed_by`).

**Files to create:**
- `backend/fastapi-app/app/models/audit.py` — `AuditLog` mapped class
- `backend/fastapi-app/migrations/versions/0007_audit_log.py`

**Model specification:**

```
AuditLog
  audit_id      Integer    PK autoincrement
  table_name    String(100) NOT NULL
  record_id     String(100) NOT NULL   -- stringified PK of the mutated record
  action_type   String(20)  NOT NULL   -- "INSERT" | "UPDATE" | "DELETE"
  old_values    JSONB       NULLABLE   -- null for INSERT
  new_values    JSONB       NULLABLE   -- null for DELETE
  changed_by    Integer     FK → AppUser.user_id  NULLABLE  -- nullable: system actions pre-auth
  changed_at    DateTime    NOT NULL DEFAULT now()
```

Notes:
- `changed_by` is nullable to allow system/script mutations before the auth layer exists (Phase 2 wires the user identity).
- `JSONB` requires `sqlalchemy.dialects.postgresql.JSONB`.
- No index on `audit_id` beyond PK; Phase 7 hardening (P7.8) can add if needed.

**Dependencies:** P1.6 (`AppUser` must exist for FK).

**Acceptance criteria:**
1. Migration 0007 applies and reverts cleanly.
2. `old_values` and `new_values` are JSONB (not JSON or Text).
3. FK to `AppUser.user_id` is declared (nullable).
4. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run mypy app
uv run ruff check app
```

---

### P1.4 — CAREER_RECORD migration (+ indexes P1.8 + constraints P1.9)
**Session:** S2
**Complexity:** M

**Objective:**
Create the `CAREER_RECORD` table with the D-041 delta (`source_id` NOT NULL), the partial-unique index enforcing one current role per alumnus (D-020), and all remaining filter/search indexes (D-028) and constraints (D-029). Tasks P1.8 and P1.9 are bundled into this migration for cohesion.

**Decisions covered:** D-020, D-021, D-028, D-029, D-041.

**Files to create:**
- `backend/fastapi-app/app/models/career.py` — `CareerRecord` mapped class
- `backend/fastapi-app/migrations/versions/0008_career_record_indexes_constraints.py`

**Model specification:**

```
CareerRecord
  career_record_id  Integer  PK autoincrement
  alumni_id         Integer  FK → Alumni.alumni_id   NOT NULL
  company_id        Integer  FK → Company.company_id  NOT NULL
  role_title        String(300) NOT NULL
  seniority         String(100) NULLABLE    -- assigned in Phase 3 (P3.9); nullable until then
  is_current        Boolean  NOT NULL DEFAULT false
  snapshot_id       Integer  FK → RefreshSnapshot.snapshot_id  NULLABLE  -- assigned at commit (Phase 4)
  source_id         Integer  FK → CaptureSource.source_id  NOT NULL       -- D-041
  captured_on       Date     NULLABLE
  created_at        DateTime NOT NULL DEFAULT now()
```

Partial-unique index (one current career record per alumnus, D-020/D-029):
```sql
CREATE UNIQUE INDEX uq_career_one_current_per_alumni
ON career_record (alumni_id)
WHERE is_current = true;
```

Filter indexes (D-028) — all in migration 0008:
```sql
CREATE INDEX idx_alumni_graduation_year    ON alumni (graduation_year);
CREATE INDEX idx_alumni_study_program      ON alumni (study_program_id);
CREATE INDEX idx_alumni_validation_status  ON alumni (validation_status);
CREATE INDEX idx_career_company            ON career_record (company_id);
CREATE INDEX idx_career_snapshot           ON career_record (snapshot_id);
CREATE INDEX idx_career_is_current         ON career_record (is_current);
CREATE INDEX idx_company_industry          ON company (industry_id);
CREATE INDEX idx_company_location          ON company (location_id);
```

Search indexes (D-028):
```sql
CREATE INDEX idx_alumni_linkedin_url       ON alumni (linkedin_url) WHERE linkedin_url IS NOT NULL;
-- canonical_name already has a unique index (implicit from UNIQUE constraint on Company)
```

Notes:
- `seniority` is nullable in Phase 1 because the seniority ladder is defined and populated in Phase 3 (P3.9). The column must exist now so Phase 3 can fill it in-place.
- `snapshot_id` is nullable for the same reason: assigned at Phase 4 commit (P4.5).
- `source_id` is NOT NULL per D-041; any import must supply it.

**Dependencies:** P1.2 (Company), P1.3 (Alumni), P1.5 (RefreshSnapshot), P1.1 (CaptureSource).

**Acceptance criteria:**
1. Migration 0008 applies and reverts cleanly.
2. Partial-unique index `uq_career_one_current_per_alumni` exists and is a partial index (WHERE is_current = true).
3. `source_id` NOT NULL constraint enforced.
4. All eight filter indexes present in `pg_indexes`.
5. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
# Supabase SQL editor:
# SELECT indexname FROM pg_indexes WHERE tablename IN ('alumni','career_record','company');
uv run mypy app
uv run ruff check app
```

---

### P1.10 — Seed STUDY_PROGRAM
**Session:** S3
**Complexity:** S

**Objective:**
Populate `STUDY_PROGRAM` with the five approved FTMM programs (`is_ftmm_valid=true`) and a sentinel non-FTMM program (`is_ftmm_valid=false`) for test coverage of rejection logic (D-003, D-004).

**Decisions covered:** D-003, D-004, D-024.

**Files to create:**
- `scripts/imports/seed_study_programs.py` — standalone uv-runnable seed script

**Seed data (exact canonical names per D-004):**

| program_name | degree_level | is_ftmm_valid |
|---|---|---|
| Technology of Data Science | S1 | true |
| Industrial Engineering | S1 | true |
| Electrical Engineering | S1 | true |
| Nanotechnology Engineering | S1 | true |
| Robotics and Artificial Intelligence Engineering | S1 | true |
| Other / Unknown | — | false |

Notes:
- Script must be idempotent: use `INSERT ... ON CONFLICT (program_name) DO NOTHING` or equivalent.
- Script reads `DATABASE_URL` from environment (same `.env` as the backend).
- Do not hardcode the connection string.

**Dependencies:** P1.1 migration applied, P1.3 migration applied (`StudyProgram` model importable).

**Acceptance criteria:**
1. Script runs without error when `DATABASE_URL` is set.
2. Script is idempotent (re-running does not create duplicates).
3. Exactly 5 rows with `is_ftmm_valid=true` in Supabase after running.
4. `mypy` + `ruff` pass on the script.

**Validation steps:**
```bash
uv run python scripts/imports/seed_study_programs.py
# Supabase: SELECT * FROM study_program;
uv run python scripts/imports/seed_study_programs.py  # idempotency check
```

---

### P1.11 — Seed CAPTURE_SOURCE
**Session:** S3
**Complexity:** S

**Objective:**
Populate `CAPTURE_SOURCE` with the four approved MVP sources and their static trust tiers per D-049.

**Decisions covered:** D-005, D-022, D-049.

**Files to create:**
- `scripts/imports/seed_capture_sources.py`

**Seed data:**

| source_type | trust_tier |
|---|---|
| Verified Faculty Record | 1 (highest trust) |
| Tracer Study | 2 |
| LinkedIn | 3 |
| Alumni Form | 4 (deferred; D-005 notes self-submitted deferred but source row must exist) |

Notes:
- Trust tier integer: lower number = higher trust (1=Verified is most trusted per D-049 ordering Verified > Tracer > LinkedIn).
- Idempotent: `ON CONFLICT (source_type) DO NOTHING`.

**Dependencies:** P1.1 migration applied.

**Acceptance criteria:**
1. Script is idempotent.
2. Four rows present; trust_tier values match the static ordering.
3. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run python scripts/imports/seed_capture_sources.py
# Supabase: SELECT source_type, trust_tier FROM capture_source ORDER BY trust_tier;
```

---

### P1.12 — Seed ROLE / PERMISSION / ROLE_PERMISSION
**Session:** S3
**Complexity:** M

**Objective:**
Populate the four roles (Admin, Data Curator, Faculty Viewer, Read Only) with a least-privilege permission matrix (D-036, D-026). This matrix is the authoritative source for Phase 2's enforcement code (P2.2–P2.3).

**Decisions covered:** D-026, D-036, D-043.

**Files to create:**
- `scripts/imports/seed_rbac.py`
- `docs/architecture/ROLE_PERMISSION_MATRIX.md` — the concrete role→permission matrix (the "Before Phase 1" artifact requested in CLAUDE_CODE_HANDOFF.md §12)

**Permission design (least-privilege per D-036):**

| Permission name | Description |
|---|---|
| `alumni:read` | View validated alumni records |
| `alumni:write` | Create/update alumni records |
| `alumni:validate` | Approve or reject pending alumni |
| `alumni:delete` | Delete/reject alumni (Admin only) |
| `career:read` | View career records |
| `career:write` | Create/update career records |
| `company:read` | View company/alias data |
| `company:write` | Create/update company and aliases |
| `import:run` | Execute import pipeline |
| `dedup:review` | Action on dedup queue |
| `snapshot:manage` | Open/finalize a refresh snapshot |
| `audit:read` | View audit log entries |
| `user:manage` | Provision/deactivate app users |
| `analytics:read` | Access aggregation/dashboard endpoints |

**Role → permission mapping:**

| Permission | Admin | Data Curator | Faculty Viewer | Read Only |
|---|:---:|:---:|:---:|:---:|
| `alumni:read` | ✓ | ✓ | ✓ | ✓ |
| `alumni:write` | ✓ | ✓ | — | — |
| `alumni:validate` | ✓ | ✓ | — | — |
| `alumni:delete` | ✓ | — | — | — |
| `career:read` | ✓ | ✓ | ✓ | ✓ |
| `career:write` | ✓ | ✓ | — | — |
| `company:read` | ✓ | ✓ | ✓ | ✓ |
| `company:write` | ✓ | ✓ | — | — |
| `import:run` | ✓ | ✓ | — | — |
| `dedup:review` | ✓ | ✓ | — | — |
| `snapshot:manage` | ✓ | ✓ | — | — |
| `audit:read` | ✓ | — | — | — |
| `user:manage` | ✓ | — | — | — |
| `analytics:read` | ✓ | ✓ | ✓ | ✓ |

Notes:
- Script must be fully idempotent.
- `ROLE_PERMISSION_MATRIX.md` must precisely match the seed script — it is the contract consumed by Phase 2.

**Dependencies:** P1.6 migration applied (Role, Permission, RolePermission tables exist).

**Acceptance criteria:**
1. All 4 roles, 14 permissions, and the full mapping inserted without error.
2. Script is idempotent.
3. `ROLE_PERMISSION_MATRIX.md` documents every permission and every role assignment.
4. `mypy` + `ruff` pass on script.

**Validation steps:**
```bash
uv run python scripts/imports/seed_rbac.py
# Supabase:
# SELECT r.role_name, p.permission_name FROM role_permission rp
# JOIN role r ON rp.role_id=r.role_id JOIN permission p ON rp.permission_id=p.permission_id
# ORDER BY r.role_name, p.permission_name;
uv run python scripts/imports/seed_rbac.py  # idempotency check
```

---

### P1.13 — Seed INDUSTRY + LOCATION reference values
**Session:** S3
**Complexity:** M

**Objective:**
Populate `INDUSTRY` with a usable starting taxonomy covering the employment sectors most likely represented in FTMM alumni data, and `LOCATION` with an initial set of Indonesian provinces/cities plus a generic "Remote / International" entry. These values are the default reference set; curators extend them when normalizing real data (Phase 3–4).

**Decisions covered:** D-009, D-010, D-018, D-019, D-042; resolves build-time Q-006 (taxonomy standard selection).

**Files to create:**
- `scripts/imports/seed_industry.py`
- `scripts/imports/seed_location.py`

**Industry taxonomy (initial set — D-042: `industry_name` granular, `sector_name` parent group):**

| industry_name | sector_name |
|---|---|
| Software Development | Technology |
| Data & Analytics | Technology |
| Artificial Intelligence & Machine Learning | Technology |
| Cybersecurity | Technology |
| Cloud & Infrastructure | Technology |
| Telecommunications | Technology |
| Electronics Manufacturing | Manufacturing & Engineering |
| Industrial Automation | Manufacturing & Engineering |
| Nanotechnology & Advanced Materials | Manufacturing & Engineering |
| Robotics & Automation | Manufacturing & Engineering |
| Oil & Gas | Energy & Resources |
| Renewable Energy | Energy & Resources |
| Mining & Metals | Energy & Resources |
| Banking & Financial Services | Finance |
| Insurance | Finance |
| Consulting | Professional Services |
| Research & Development | Education & Research |
| Higher Education | Education & Research |
| Government & Public Sector | Public Sector |
| Healthcare | Healthcare |
| Other / Unclassified | Other |

Notes on taxonomy selection:
- Chosen to reflect FTMM's five programs (Data Science, Industrial Engineering, Electrical Engineering, Nanotech, Robotics) and Surabaya/Indonesian job market reality.
- `Other / Unclassified` catch-all is required for normalization completeness.
- Curators add industry rows as needed; seed values are not exhaustive.
- Idempotent on `industry_name` unique key.

**Location initial set (Indonesia-focused):**
- Key Indonesian provinces: East Java, West Java, DKI Jakarta, Banten, Central Java, DI Yogyakarta, Bali, South Sulawesi, North Sumatra, South Sumatra, Riau.
- Key cities per province (at minimum: Surabaya, Jakarta, Bandung, Semarang, Yogyakarta, Malang, Denpasar, Makassar, Medan).
- Country: "Indonesia" for all of the above.
- One catch-all row: `country="Other"`, `city=NULL`, `province=NULL`, `region="International"`.
- One remote row: `country="Remote"`, `city=NULL`, `province=NULL`, `region="Remote"`.
- Idempotent: check on `(country, province, city)` composite uniqueness (handled in script logic, not a DB constraint).

**Dependencies:** P1.1 migration applied (Industry, Location tables exist).

**Acceptance criteria:**
1. At least 20 industry rows with all four fields populated.
2. `Other / Unclassified` industry row present.
3. At least 10 Indonesian city/province location rows + the Remote and International catch-alls.
4. Both scripts idempotent.
5. `mypy` + `ruff` pass.

**Validation steps:**
```bash
uv run python scripts/imports/seed_industry.py
uv run python scripts/imports/seed_location.py
# Supabase: SELECT sector_name, COUNT(*) FROM industry GROUP BY sector_name ORDER BY sector_name;
# Supabase: SELECT country, COUNT(*) FROM location GROUP BY country;
```

---

### P1.14 — Audit-write service contract
**Session:** S4
**Complexity:** S

**Objective:**
Define the application-level audit-write service: a typed function `write_audit_entry(...)` that takes a database session, table name, record ID, action type, old/new values, and optional user ID, and inserts into `AUDIT_LOG`. No actual wiring to business operations yet — that is Phase 4 (P4.6). This task defines the contract so Phase 3 can import it and Phase 4 can wire it without rework.

**Decisions covered:** D-025, D-031, D-036.

**Files to create:**
- `backend/fastapi-app/app/services/__init__.py`
- `backend/fastapi-app/app/services/audit.py`

**Service contract:**

```python
# app/services/audit.py

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit_entry(
    session: Session,
    *,
    table_name: str,
    record_id: str,
    action_type: str,          # "INSERT" | "UPDATE" | "DELETE"
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    changed_by: int | None = None,  # AppUser.user_id; None for system actions
) -> AuditLog:
    """
    Insert one audit entry into AUDIT_LOG.

    The caller is responsible for committing the session. This function only
    constructs and adds the entry — it does not flush or commit.
    """
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action_type=action_type,
        old_values=old_values,
        new_values=new_values,
        changed_by=changed_by,
    )
    session.add(entry)
    return entry
```

Notes:
- The function must NOT commit the session — it is the caller's responsibility. This allows callers to batch the audit entry with the mutating operation in a single transaction (Phase 4 pattern).
- `action_type` is a plain string here; Phase 4 can introduce a `Literal["INSERT","UPDATE","DELETE"]` type alias if useful.
- Keep it simple: no retry, no async, no queue. Volume is batch-write, low-concurrency (D-027).

**Files to add tests for:**
- `backend/fastapi-app/tests/test_audit_service.py` — unit test using an in-memory SQLite session (not Supabase) verifying the entry is added to the session without commit.

**Dependencies:** P1.7 (AuditLog model must exist).

**Acceptance criteria:**
1. `write_audit_entry` is importable from `app.services.audit`.
2. Calling it adds exactly one `AuditLog` row to the session (without flushing/committing).
3. Unit test passes with `uv run pytest tests/test_audit_service.py`.
4. `mypy app` passes (fully typed).
5. `ruff check app` passes.

**Validation steps:**
```bash
uv run pytest tests/test_audit_service.py -v
uv run mypy app
uv run ruff check app
uv run black --check app tests
```

---

## Phase 1 Exit Checklist

Run these in order after all tasks complete:

```bash
# 1. Full migration stack
uv run alembic upgrade head
# Expected: migrations 0002–0008 applied; no errors.

# 2. Seed all reference data
uv run python scripts/imports/seed_study_programs.py
uv run python scripts/imports/seed_capture_sources.py
uv run python scripts/imports/seed_rbac.py
uv run python scripts/imports/seed_industry.py
uv run python scripts/imports/seed_location.py

# 3. Verify seed idempotency (re-run; must produce no duplicates)
uv run python scripts/imports/seed_study_programs.py
uv run python scripts/imports/seed_capture_sources.py
uv run python scripts/imports/seed_rbac.py
uv run python scripts/imports/seed_industry.py
uv run python scripts/imports/seed_location.py

# 4. Quality gates
uv run ruff check app tests scripts
uv run black --check app tests scripts
uv run mypy app
uv run pytest -v

# 5. Health endpoint still green (schema changes must not break Phase 0)
uv run uvicorn app.main:app --port 8000 &
curl http://localhost:8000/health
# Expected: {"status":"ok","app_env":"local","database":"connected"}
```

**Phase 1 is DONE when:**
- [ ] `alembic upgrade head` builds all 8 migrations cleanly on Supabase (0001–0008).
- [ ] `alembic downgrade base` then `alembic upgrade head` round-trips without error.
- [ ] All 5 seed scripts run idempotently.
- [ ] Supabase shows: 5 FTMM study programs, 4 capture sources, 4 roles, 14 permissions, ≥20 industries, ≥12 locations.
- [ ] `ROLE_PERMISSION_MATRIX.md` present in `docs/architecture/`.
- [ ] `write_audit_entry` importable and tested.
- [ ] `uv run pytest` passes (old health test + new audit test).
- [ ] `ruff` + `black` + `mypy` all green.
- [ ] `/health` endpoint still returns `{"status":"ok"}`.
- [ ] No `.env` values committed; no hardcoded connection strings in any file.

---

## Operator Checklist (before handing to implementation agent)

- [ ] P0.8 complete: Supabase project is provisioned and `DATABASE_URL` (pooler URI, psycopg format) is available.
- [ ] Backend `.env` file has `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` filled in.
- [ ] `uv run alembic upgrade head` (from `backend/fastapi-app/`) applies the baseline migration `0001_baseline` successfully against Supabase.
- [ ] Review `docs/architecture/ROLE_PERMISSION_MATRIX.md` after P1.12 and confirm the permission mapping is correct before starting Phase 2.

---

## What Must Be Prepared Before Phase 2

Per CLAUDE_CODE_HANDOFF.md §12:

- [ ] **ER diagram** — a visual/textual entity-relationship diagram reflecting all 14 tables after Phase 1 is applied. Recommended location: `docs/architecture/ER_DIAGRAM.md`.
- [ ] **Role → permission matrix** — produced as `docs/architecture/ROLE_PERMISSION_MATRIX.md` by P1.12. Must be reviewed and confirmed by the operator before Phase 2 JWT/RBAC enforcement is coded.

---

## Scope Guardrails (never implement in Phase 1)

- No FastAPI endpoints that serve data (beyond the existing `/health`).
- No JWT verification, no auth middleware.
- No import pipeline logic.
- No aggregation queries.
- No frontend changes.
- No AI/ML, fuzzy matching, caching, real-time, microservices.
- No new env vars (all necessary ones are already in `.env.example`).
- All matching/validation decisions remain curator-controlled (implemented in Phase 3–4).
