# Technical Decisions Summary

**Source:** DECISIONS.md (D-001–D-051), IMPLEMENTATION_ROADMAP.md, CLAUDE_CODE_HANDOFF.md  
**Purpose:** Concise engineering reference — the "why" behind every major architectural choice.  
**Rule:** Every implementation choice traces to at least one decision ID. If a task isn't here, it wasn't approved scope.

---

## Section 1 — Product Scope (D-001–D-010)

### D-001: Analytics & reporting only
The system answers "where do alumni work and in what roles?" It does not manage alumni records
transactionally, process applications, or serve as a CRM. This boundary prevents scope creep
and keeps the data model clean.

### D-002: No AI/ML anywhere
No AI assistants, chatbots, RAG, recommendation engines, LLMs, confidence scoring, or
predictive analytics. **Ever.** This is a permanent non-goal, not a deferral.  
**Rationale:** Accreditation bodies require explainable, auditable reporting. AI-derived outputs
cannot be explained to a standards body. Deterministic + curator-controlled = auditable.

### D-003/D-004: Strict 5-program validity rule
An alumnus is valid only if their record contains "Universitas Airlangga" AND one of exactly
5 approved program names. Anything else is excluded.  
**Programs:** Technology of Data Science, Industrial Engineering, Electrical Engineering,
Nanotechnology Engineering, Robotics and Artificial Intelligence Engineering.  
**Rationale:** Prevents data contamination from other universities or programs that appear in
LinkedIn/tracer exports alongside FTMM graduates.

### D-005: Three MVP data sources
LinkedIn exports, Verified Faculty Records, Tracer Study surveys. No real-time scraping,
no self-submitted alumni forms (deferred), no API integrations.  
**Rationale:** These are the sources FTMM actually has. Scope is bounded to what exists.

### D-006/D-007: Quarterly snapshot model
Data is refreshed quarterly. The Snapshot Quarter is a first-class filter dimension — users
can see the dashboard as it was at any past quarter.  
**Rationale:** Alumni career data changes slowly. Real-time sync is unnecessary complexity.
Point-in-time reporting is required for accreditation (the number must be stable six months later).

### D-008/D-009/D-010: Normalization is in-scope
Company normalization, industry classification, and geographic mapping are required features,
not optional quality improvements.  
**Rationale:** Without normalization, "Google", "PT Google Indonesia", and "Google LLC" are three
separate companies in analytics. The dashboard becomes useless.

---

## Section 2 — Data Model (D-017–D-029, D-040–D-049)

### D-017: Company + alias normalization
`COMPANY` holds canonical names. `COMPANY_ALIAS` maps raw spellings to canonical companies.
Many raw strings → one canonical entity.  
**In practice:** when a new employer name appears at import time, the service looks it up in
`COMPANY_ALIAS`. If found, it links to the canonical company. If not, it creates both.

### D-018/D-042: Industry at company level; flat table with two columns
Industry is attached to `COMPANY`, not to `CAREER_RECORD`. An alumnus's industry is derived
from their current employer.  
Industry is a flat `INDUSTRY` table with `industry_name` (granular) and `sector_name` (rollup).
**No hierarchy table** — one join, two grouping levels, same source of truth.  
**Rationale:** Industry follows the company, not the career. If a company changes sector,
it propagates to all associated alumni. One table is simpler than parent-child taxonomy.

### D-019: Location normalized in a separate table
`LOCATION` (country/province/city/region) is a reference table. `COMPANY` has a `location_id`
FK. Raw location strings are resolved at import time.  
**No `country` column on `COMPANY`** (removed — was a D-021 clarification).

### D-020: Career history preserved; one current role enforced
`CAREER_RECORD` is append-only — an alumnus can have N records (full history).  
Exactly one `is_current = true` per alumnus is enforced by a **partial unique index**:
`CREATE UNIQUE INDEX ON career_record (alumni_id) WHERE is_current = true`.  
This is a database-level invariant, not just application logic.

### D-021: Snapshot model at career-record grain
`REFRESH_SNAPSHOT` stores the quarter label. `CAREER_RECORD.snapshot_id` tags which import
the record came from. Master entities (company, industry, alumni) are **not** versioned.  
**Implication:** A change to a company's industry classification propagates retroactively to
all past snapshots. This is an accepted MVP limitation.

### D-022/D-049: Static trust tier on CAPTURE_SOURCE
`CAPTURE_SOURCE` has a trust tier field (formerly `confidence_level`). It is static and
curator-assigned: Verified Faculty Record > Tracer Study > LinkedIn.  
It is **never computed**, never auto-decides inclusion. It is a human-readable priority
signal for conflict resolution when two sources disagree on an alumnus's details.

### D-023/D-044: Alumni identity is UUID; LinkedIn URL is nullable + partial-unique
`ALUMNI.public_id` is the system identity (UUID, always present, always unique).  
`ALUMNI.linkedin_url` is nullable. When present, it must be unique — enforced with a
partial unique index: `WHERE linkedin_url IS NOT NULL`.  
**Rationale:** Not all alumni have LinkedIn profiles. Identity cannot depend on a field
that might be absent.

### D-024/D-047: Curator validation gate; validated-only analytics
`ALUMNI.validation_status` is an enum: `{pending, validated, rejected}`.  
- `pending` — imported, awaiting curator review.  
- `validated` — explicitly approved by a Data Curator. The only status that enters analytics.  
- `rejected` — excluded, but retained for audit and anti-churn (can be re-evaluated).  
  
The `build_alumni_where()` function **unconditionally** prepends `validation_status = 'validated'`
to every analytics query. There is no flag, no bypass, no code path that shows unvalidated data.

### D-025: Application-level audit logging
Every data mutation writes to `AUDIT_LOG` via `write_audit_entry()` in service code.  
`AUDIT_LOG` captures: table name, record ID, action type, old values (JSONB), new values (JSONB),
changed_by (APP_USER FK), changed_at.  
**Why application-level, not DB triggers?** Because triggers cannot capture the authenticated
actor or structure the diffs into meaningful JSON — the application layer knows both.

### D-026: Four-role RBAC
Roles: Admin, Data Curator, Faculty Viewer, Read Only.  
12 permissions (analytics:read, import:run, alumni:validate, alumni:read, etc.).  
38 role-permission assignments in `ROLE_PERMISSION`.  
Least-privilege: Faculty Viewer can read analytics but cannot import or validate.

### D-029: Database constraints as invariants
Unique `public_id`, partial-unique `linkedin_url`, unique `canonical_name` on company,
partial-unique `is_current` on career record.  
**Philosophy:** constraints the database can enforce should be enforced in the database,
not only in application code. Constraints survive application bugs.

### D-040: University stored as a column, enforced in workflow
`ALUMNI.university` is a text column (default "Universitas Airlangga").  
University matching is enforced in the curator validation workflow (program_matcher service),
not as a relational entity or FK.  
**Rationale:** Adding a University entity creates a join that adds no value — FTMM only
ever ingests its own graduates.

### D-041/D-046: Source provenance on both ALUMNI and CAREER_RECORD
`ALUMNI.source_id` FK (primary provenance — where this person was first discovered).  
`CAREER_RECORD.source_id` FK NOT NULL (provenance of each career record — required).  
**Rationale:** Different career records for the same alumnus can come from different sources.
Provenance at the career-record grain is required for trust-tier conflict resolution.

### D-045: Deterministic two-tier deduplication
**Tier 1:** If `linkedin_url` matches exactly → auto-link to existing alumnus. No human needed.  
**Tier 2:** If `normalized(full_name) + study_program_id + graduation_year` matches →
create a `DedupCandidate` entry for curator review. Human decides: confirm-merge or keep-separate.  
**No fuzzy matching, no AI.** Every dedup decision is either a deterministic rule or a human action.

### D-048: "Employed vs Not Reported" — not "unemployment rate"
An alumnus with a current `CAREER_RECORD` (`is_current = true`) is **Employed**.  
An alumnus without one is **Not Reported** — not "Unemployed".  
`not_reported_count = total_validated - employed_count`.  
The word "unemployed" and the field `unemployment_rate` **do not exist** in any Pydantic
schema or API response. This is enforced structurally, not by convention.  
**Rationale:** Absence of a career record in the database does not mean the person has no job.
It means the data isn't there. Asserting unemployment from missing data is epistemically wrong
and potentially harmful to accreditation reporting.

---

## Section 3 — Architecture (D-031–D-039)

### D-031: Single FastAPI gateway — the most important architecture decision
```
Browser → Next.js → FastAPI → PostgreSQL (Supabase)
```
The frontend **never** reads from or writes to the database directly.  
All data access, all business rules, all validation, all RBAC enforcement lives in FastAPI.  
**Benefits:**
- One place to enforce all invariants (validation gate, audit log, rate limits).
- Frontend can be rewritten without touching business logic.
- API is the contract; both sides can evolve independently.

### D-032/D-043: Supabase Auth = authentication; app DB = authorization
**Split design:**  
- Supabase Auth handles login, session management, JWT issuance. The JWT carries only the
  user's UUID (`sub`) and expiry (`exp`). Roles are **never in the JWT**.  
- FastAPI receives the JWT, verifies the signature with `SUPABASE_JWT_SECRET`, extracts the UUID,
  looks up `APP_USER` by that UUID, loads `ROLE` and `ROLE_PERMISSION` from the app DB.  
- Permissions are loaded fresh on every request from the app DB.  
**Why this split?**  
Supabase Auth is managed infrastructure — fast to provision, handles MFA, session refresh,
password reset. But roles belong in the application: they can change instantly without
invalidating sessions, they live in the same DB as the rest of the data, and they never
need to be baked into a token.

### D-033/D-034: Manual import; quarterly refresh
Import is a curator action (upload a file), not an automated pipeline.  
Quarterly refresh is a workflow: open snapshot → import → validate → commit.  
**No real-time sync**, no webhooks, no event streaming.  
**Rationale:** Alumni career data changes slowly. The cost and complexity of real-time sync
is entirely unjustified at quarterly cadence.

### D-035: Deploy mapping
Frontend → Vercel. Backend → Railway. DB + Auth → Supabase.  
Each platform gets only the secrets it needs. Backend secrets never reach the browser.

### D-036: Security model
- DB never exposed directly; all rules in FastAPI.
- Least privilege per role.
- Every mutation audited.
- RBAC enforced per endpoint via `require_permission()` dependency.

### D-037: Monorepo layout
```
frontend/nextjs-app/
backend/fastapi-app/
database/{migrations,schema}/
docs/{architecture,decisions}/
scripts/{imports,maintenance}/
data/synthetic/
```
Single repository, single CI pipeline, shared governance docs.

### D-038/D-030: Explicit exclusions (permanent non-goals)
No Kubernetes, no microservices, no event-driven architecture, no Kafka, no CQRS,
no distributed systems, no real-time streaming, no AI/ML of any kind.  
These are not deferred — they are explicitly out of scope for this project.

---

## Section 4 — Security (D-036, D-043, D-050, D-051)

### JWT verification in detail
`verify_jwt()` in `app/dependencies/auth.py`:
1. Extracts `Bearer <token>` from `Authorization` header.
2. Decodes with `SUPABASE_JWT_SECRET`, algorithm HS256.
3. Validates `sub` (non-empty string) and `exp` (integer).
4. Does NOT validate `aud` — Supabase includes `"authenticated"` as audience, but the
   secret is already project-scoped, so audience validation would be redundant.
5. Raises HTTP 401 on any failure (expired, invalid signature, missing claims).

### Permission enforcement in detail
`require_permission("analytics:read")` returns a dependency function that:
1. Calls `get_current_user()` (which calls `verify_jwt()`).
2. Checks `permission in user.permissions` (frozenset loaded from `ROLE_PERMISSION`).
3. Raises HTTP 403 if absent.
4. Returns the `AuthenticatedUser` so route handlers can use it (e.g. for `changed_by`).

### D-050/D-051: PII and legal posture
D-050: No in-app LinkedIn scraping. LinkedIn data enters only as offline-collected exports.  
D-051: PII safeguards — RBAC, data minimization, retention aligned to quarterly snapshots,
AUDIT_LOG accountability.  
Both decisions carry **external legal preconditions** (R-001: LinkedIn ToS, R-002: UU PDP
consent). Development uses synthetic data only. The pipeline is production-ready; the live
PII load waits on institutional legal sign-off.

---

## Section 5 — Key Implementation Patterns

### The analytics filter pipeline
Every analytics endpoint receives a `filters: AnalyticsFilters` object (dataclass with 6 fields).
Three functions build WHERE clauses:
- `build_alumni_where(filters)` → always includes `validation_status = 'validated'`
- `build_career_where(filters)` → applies industry, company, snapshot, year, program
- `build_country_clause(filters)` → returns a self-contained `IN` subquery for country filter

Country is isolated because it requires a Company→Location join that `build_career_where()`
does not perform. The `IN` subquery is self-contained and composes with any `CareerRecord`
query without requiring an explicit join at each call site.

### The commit pipeline
`commit_batch()` in `app/services/commit.py`:
1. Receives a batch of validated, normalized staged rows.
2. For each row: resolves or creates Alumni (using public_id / linkedin_url).
3. Deactivates the previous current career record (`is_current = false`).
4. Inserts a new CareerRecord (`is_current = true`, `snapshot_id` = current quarter).
5. Returns the result summary.
6. Never calls `session.commit()` — the route layer owns the transaction (D-031).

### Rate limiter as a FastAPI dependency
`import_rate_limit(request: Request) -> None` is a FastAPI dependency that:
- Extracts `request.client.host` as the rate-limit key.
- Checks a sliding window (last 60 seconds) for the IP.
- Raises HTTP 429 if ≥ 10 calls in the window.
- Is registered with `Depends()` in the import endpoint signature.
- **Tests override it** with `app.dependency_overrides[import_rate_limit] = lambda: None`
  to avoid test isolation issues with the shared in-memory counter.

### The dedup candidate key
Tier-2 deduplication matches on:
```python
normalize(full_name) + str(study_program_id) + str(graduation_year)
```
Where `normalize()` = lowercase + strip + collapse whitespace + remove honorifics.  
If the key matches an existing alumnus, a `DedupCandidate` entry is created.  
The curator sees it in the review queue and decides confirm-merge or keep-separate.

---

## Section 6 — Decisions That Were Challenged and Upheld

### "Why not use Supabase Row Level Security (RLS)?"
RLS would put business rules in the database, fragmenting them across FastAPI and Postgres.
D-031 says FastAPI is the single business-logic gateway. RLS was explicitly rejected.

### "Why not store roles in the JWT?"
Because roles would be stale — a role change wouldn't take effect until the token expires.
D-043 says roles come from the app DB on every request. Fresh, instant, consistent.

### "Why not use an AI/fuzzy matcher for deduplication?"
D-045 and D-002. Fuzzy matches produce probabilistic decisions that can't be explained to
an accreditation body. Two people with the same name and program are possible — the curator
must decide, not an algorithm.

### "Why not show an unemployment rate?"
D-048. Absence of a career record does not mean unemployment. The data has coverage
limitations — alumni who changed jobs, aren't on LinkedIn, or weren't in the tracer study
cohort won't have records. "Not Reported" is the only epistemically defensible label.

### "Why not use Django or Django REST Framework?"
Not an approved decision, but the reasoning: FastAPI's dependency injection model makes
RBAC wiring idiomatic (one `Depends()` per route). Pydantic v2 gives free validation and
OpenAPI schema generation. SQLAlchemy 2.0 with FastAPI is cleaner than Django ORM + DRF
for a read-heavy analytics API.

---

## Decision Quick-Reference Index

| ID | Topic | Key point |
|----|-------|-----------|
| D-001 | Scope | Analytics only; no transactional features |
| D-002 | No AI | Permanent non-goal |
| D-003/004 | Validity | Strict 5-program match required |
| D-005 | Sources | 3 MVP sources; no scraping |
| D-006 | Cadence | Quarterly; no real-time |
| D-007 | Snapshot filter | Quarter is a first-class filter dimension |
| D-008/009/010 | Normalization | Company, industry, location — all required |
| D-017 | Company model | Alias → canonical |
| D-018/042 | Industry model | At company level; flat table with 2 columns |
| D-019 | Location model | Normalized LOCATION table |
| D-020 | Career records | Append-only; partial-unique `is_current` |
| D-021 | Snapshots | Career-record grain; master entities not versioned |
| D-022/049 | Provenance | Static trust tier on CAPTURE_SOURCE |
| D-023/044 | Identity | public_id UUID; linkedin_url nullable+partial-unique |
| D-024/047 | Validation | Curator gate; only validated in analytics |
| D-025 | Audit | Application-level AUDIT_LOG; every mutation captured |
| D-026 | RBAC | 4 roles, 12 permissions |
| D-029 | Constraints | DB-level invariants for critical uniqueness rules |
| D-031 | Gateway | FastAPI = single business-logic gateway |
| D-032/043 | Auth split | Supabase Auth = authn; app DB = authz |
| D-033/034 | Workflow | Manual import; quarterly refresh |
| D-035 | Deploy | Frontend→Vercel; Backend→Railway; DB→Supabase |
| D-036 | Security | RBAC; audit; least privilege; no direct DB access |
| D-037 | Monorepo | frontend/ backend/ database/ docs/ scripts/ |
| D-038/030 | Exclusions | No K8s, microservices, streaming, AI |
| D-040 | University | Text column on ALUMNI; enforced in workflow |
| D-041/046 | Provenance FKs | source_id on both ALUMNI and CAREER_RECORD |
| D-044 | Dedup identity | Candidate key = name+program+year |
| D-045 | Dedup tiers | Tier 1: URL exact; Tier 2: key → curator queue |
| D-048 | Employment | "Employed vs Not Reported"; no unemployment_rate |
| D-050/051 | Legal/PII | No scraping; synthetic data until R-001/R-002 cleared |
