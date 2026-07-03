# Portfolio Demo Guide

**Project:** FTMM Alumni Intelligence Dashboard  
**Audience:** Interviewers, hiring managers, technical reviewers, academic faculty

---

## Demo Scenario

> "FTMM, a new engineering faculty at Universitas Airlangga, had no way to track where its
> graduates ended up. Alumni career data was scattered across manual spreadsheets, LinkedIn
> exports, and tracer study reports — with no single source of truth and no way to answer
> faculty questions about employment outcomes. I built a full-stack analytics platform that
> solves this from data ingestion through to an interactive dashboard."

The demo follows a faculty member who wants to answer: *"Where are our Data Science graduates
working two years after graduation, and what seniority levels have they reached?"*

---

## Demo Script — 12 Minutes

### Minute 0–1: Problem framing (verbal, no screen)

> "Before I show the dashboard, let me explain why this is hard. Faculty management needs to
> report alumni outcomes to accreditation bodies. But the data comes from three incompatible
> sources — LinkedIn exports, verified faculty records, and tracer study surveys. Each source
> uses different company name spellings, program name variants, and location formats. And they
> overlap — the same alumnus may appear in all three with slightly different data.
>
> The challenge isn't just building a dashboard. It's building the entire data pipeline
> that turns messy, overlapping source data into trustworthy analytics — without ever
> asserting things we don't know."

---

### Minute 1–2: Architecture overview (brief, from README or architecture diagram)

Pull up the README or a simple architecture diagram.

> "The system is three layers: a Next.js frontend on Vercel, a FastAPI backend on Railway,
> and a PostgreSQL database on Supabase. The key constraint is that the frontend never touches
> the database directly — all data flows through the FastAPI gateway. This enforces consistent
> business rules and gives us a single place to audit every write.
>
> I built this as a monorepo with strict quality gates: mypy strict mode, 647 pytest tests,
> and a vitest frontend test suite — all gated by GitHub Actions CI."

---

### Minute 2–3: Login and role system

Open the Vercel URL → show the `/login` page.

> "The system uses Supabase Auth for authentication — it issues a JWT — but authorization
> is entirely in the application database. FastAPI verifies the JWT, looks up the user's
> role in our app DB, and enforces permissions per request. Roles never come from the JWT
> claims. This separation is important: it means we can change someone's permissions instantly
> without invalidating their session."

Log in with the Admin account. Dashboard loads.

> "There are four roles — Admin, Data Curator, Faculty Viewer, and Read Only. What I'm
> showing you now is the Admin view, which includes both the analytics dashboard and the
> curator tools."

---

### Minute 3–5: The data pipeline (curator side)

Navigate to **Curator → Import**.

> "This is where it starts. A curator uploads a CSV or XLSX — a tracer study export or
> a LinkedIn dataset. The parser stages every row without touching the main alumni tables.
> The import is atomic: if anything goes wrong, the entire batch rolls back."

Show a completed import batch summary (from the synthetic data load).

> "Each row goes through four normalization steps: program matching — which maps 20+ spelling
> variants of 'Data Science Technology' to the canonical program name; company normalization —
> which resolves 'PT Tokopedia', 'Tokopedia Indonesia', 'tokopedia.com' to a single canonical
> company; location normalization; and role/seniority classification — a deterministic ladder
> from Junior to Director based on the job title."

Navigate to **Curator → Validation**.

> "After import, rows are `pending`. The curator reviews each one — they can see the matched
> program, the university field, and the source — and explicitly validates or rejects. Only
> `validated` alumni ever appear in analytics. This is the key invariant. I could not find a
> way to accidentally show unvalidated or incorrect data in the dashboard."

---

### Minute 5–7: Deduplication

Navigate to **Curator → Dedup**.

> "Deduplication is two-tier. Tier 1: if a LinkedIn URL matches exactly, we auto-link the
> new record to the existing alumnus. Tier 2: if the normalized name plus program plus
> graduation year matches, it goes into this review queue for the curator to confirm-merge
> or keep-separate. No fuzzy matching, no AI — it's fully deterministic and fully
> curator-controlled. The curator decides; the system executes."

---

### Minute 7–10: Analytics dashboard

Navigate to **Overview** (`/`).

> "The dashboard shows only validated alumni. These four KPIs — total alumni, companies,
> industries, countries — update instantly when you change the filter."

Apply the **Study Program** filter: select "Technology of Data Science".

> "Now we're looking only at Data Science graduates. Notice everything updates — the KPIs,
> the alumni-by-graduation-year chart. Let me show you career outcomes for this cohort."

Navigate to **Career Outcomes** (`/careers`).

> "This is a deliberate design choice I want to highlight. The dashboard shows 'Employed vs
> Not Reported' — not 'employed vs unemployed'. We can't assert that an alumnus without a
> current career record in our database is unemployed. They might have changed jobs, or just
> not be in any of our data sources. This distinction mattered to the faculty — they wanted
> the reporting to be accurate, not misleading. So I hard-coded this semantic into the system:
> the word 'unemployed' and the phrase 'unemployment rate' cannot appear in any API response."

Show the seniority distribution chart.

> "This seniority breakdown is derived deterministically from job titles using a classification
> ladder. Junior → Mid-level → Senior → Lead → Director. I can show you the algorithm — it's
> 91 test cases in the test suite."

Navigate to **Industry Breakdown** (`/industries`).

> "Industry is attached at the company level — the INDUSTRY table is linked to COMPANY, not
> to CAREER_RECORD. So when a company's industry classification is corrected, it propagates
> to every alumnus who worked there. The chart shows both granular industry names and sector
> rollups."

Navigate to **Geography** (`/geography`).

> "Country and city distribution. Every location in the database went through a normalization
> step to resolve 'Jakarta', 'DKI Jakarta', 'Jakarta Pusat' to canonical forms."

---

### Minute 10–11: Point-in-time reporting

Change the **Snapshot Quarter** filter between `2025-Q1` and `2025-Q2`.

> "This is the snapshot model. Every career record is tagged with the quarter it was imported
> under. When I switch from Q1 to Q2, the dashboard shows the state of the world as of that
> quarter — not the current state. This is critical for accreditation reporting: the faculty
> needs to say 'as of Q1 2025, our employment rate was X', and that number must be stable
> and reproducible six months later."

---

### Minute 11–12: Alumni directory and technical closing

Navigate to **Directory** (`/directory`).

> "The directory is searchable and respects all the same filters. Click any row to see the
> full profile with career history annotated by snapshot."

Click an alumnus row to show the detail page.

Close with one of:

> "The backend has 647 pytest tests — the test suite is as long as some production codebases.
> The reason is that the data engine is where errors are catastrophic: a bug in the dedup
> logic could silently merge two different people, a bug in the validation gate could let
> unvalidated data into analytics. Tests are the only way to prove the invariants hold."

or

> "Every piece of this is deployed continuously via GitHub Actions. The CI runs ruff, black,
> mypy strict, pytest, vitest, ESLint, TypeScript typecheck, and a Next.js production build.
> Nothing merges to main without all of those passing."

---

## Features to Showcase (priority order)

1. **The invariant that only `validated` alumni appear in analytics** — the most important design decision; emphasize this explicitly.
2. **"Employed vs Not Reported" semantics** — not an accident; a deliberate epistemic choice backed into the API schema (the field `unemployment_rate` does not exist in any response).
3. **Snapshot-based point-in-time reporting** — filter by quarter, get stable historical data.
4. **The deterministic two-tier dedup system** — no AI, no fuzzy matching, fully curator-controlled.
5. **Company normalization** — aliases resolved at ingest time; industry propagates from company.
6. **RBAC** — JWT from Supabase, permissions from app DB. Show a Faculty Viewer seeing analytics but getting 403 on curator endpoints.
7. **Atomic import + audit log** — every write is transactional and auditable.
8. **Test suite size** — 647 backend tests, 23 frontend tests, strict mypy. Portfolio-grade quality bar.

---

## Sample Analytics to Explain

Use these talking points when showing the charts:

### Overview KPIs
> "Total alumni here is only the validated cohort — 100 from Q1 and 120 from Q2, of which
> some are carry-forward alumni with updated career records. Companies is the count of
> distinct canonical employers — after normalization, not raw counts."

### Career Outcomes — Employed split
> "The employed count comes from alumni who have a current career record — `is_current = true`
> in the CAREER_RECORD table. The 'Not Reported' count is the difference: total validated
> minus employed. We explicitly document this as a data-coverage limitation, not an employment
> outcome claim."

### Seniority distribution
> "The seniority classification uses 91 deterministic rules — things like: if the title
> contains 'Senior' or 'Sr.', it maps to Senior; if it contains 'VP' or 'Director', it maps
> to Director. I wrote this as a pure function with exhaustive test coverage because it's
> the kind of thing that looks simple but has many edge cases."

### Industry breakdown
> "The sector grouping (e.g. 'Technology', 'Finance', 'Manufacturing') is a rollup of the
> granular industry names. Both live in the same INDUSTRY table — `industry_name` for the
> granular view, `sector_name` for the rollup. This was a schema design decision (D-042)
> made early to avoid a separate sector table."

### Snapshot Quarter filter
> "Switching between quarters is point-in-time reporting. It uses the `snapshot_id` foreign
> key on CAREER_RECORD. The master entities — alumni, companies — are not versioned; only
> the career records are. This is an accepted MVP limitation: if a company's industry
> classification changes, it changes retroactively across all snapshots."

---

## Screenshots to Capture

Capture these in order. Use a 1280×800 or 1440×900 browser window. Dark mode if your theme supports it.

| # | Page | What to show |
|---|------|-------------|
| 1 | Overview (`/`) | All 4 KPIs populated; alumni-by-graduation-year bar chart |
| 2 | Overview with filter | Study Program filter active; numbers updated |
| 3 | Career Outcomes (`/careers`) | Employed vs Not Reported donut; seniority distribution bar |
| 4 | Industry Breakdown (`/industries`) | Both industry granular chart and sector rollup |
| 5 | Geography (`/geography`) | Country distribution; city breakdown |
| 6 | Directory (`/directory`) | Table with search field; multiple rows visible |
| 7 | Alumnus detail (`/directory/[id]`) | Profile card + career history with snapshot label |
| 8 | Curator Import (`/curator/import`) | Upload form; batch summary after import |
| 9 | Validation queue (`/curator/validation`) | Pending alumni list with validate/reject buttons |
| 10 | Snapshot Quarter switcher | Filter bar with Q1 selected; then Q2 — show the number change |

---

## GIF Recommendations

Short GIFs (5–8 seconds each) are the most effective for README/portfolio pages.

| GIF | How to record |
|-----|--------------|
| **Filter chain reaction** | Click Study Program filter → watch KPIs + chart update simultaneously |
| **Snapshot quarter switch** | Switch from Q1 to Q2 → numbers animate to higher values |
| **Directory search** | Type a name in the search field → rows filter in real time |
| **Login → dashboard** | From login page → submit → Overview page loads |
| **Import flow** | Upload a CSV → batch summary appears with row counts |

Record with [ScreenToGif](https://www.screentogif.com/) (Windows), [Kap](https://getkap.co/) (macOS), or [LICEcap](https://www.cockos.com/licecap/).

Optimize with [Squoosh](https://squoosh.app/) or `gifsicle --optimize=3`. Target < 3 MB per GIF.

---

## Resume Bullet Suggestions

Choose 3–5 of these. Customize the numbers to match your actual deployment.

**Impact / outcome framing:**
- Built a full-stack alumni career analytics platform (FastAPI + Next.js + PostgreSQL) handling the complete ETL pipeline from raw CSV imports through deterministic deduplication, curator validation, and snapshot-based point-in-time reporting.
- Designed and implemented a 9-migration Alembic schema covering 16 tables with RBAC, audit logging, and snapshot-versioned career records; enforced zero-regression quality via 647 pytest tests under mypy strict mode.
- Implemented deterministic alumni deduplication without AI: two-tier system (exact URL match → auto-link; candidate key → curator review queue), eliminating fuzzy-matching fragility while keeping the curator in control.
- Architected an analytics gateway (FastAPI) that enforces the invariant that only curator-validated alumni appear in any dashboard view — preventing data-quality errors from surfacing to faculty stakeholders.
- Built a structured JSON logging layer, sliding-window rate limiter, and HTTP security headers from scratch with no additional dependencies; deployed on Railway + Vercel with migration-on-deploy automation.

**Technical specificity framing:**
- Resolved a multi-source data quality problem: company normalization (alias → canonical), program name variant mapping (20+ aliases per program), location normalization, and role/seniority classification — all deterministic, all tested.
- Implemented snapshot-based point-in-time reporting at the career-record grain; faculty can query "as of 2025-Q1" and get a stable, reproducible answer months later.
- Configured CI/CD (GitHub Actions) running ruff, black, mypy, pytest, vitest, ESLint, TypeScript typecheck, and Next.js production build — all required to pass before merge.
- Documented the "Employed vs Not Reported" epistemics in the API contract: `unemployment_rate` is a structurally absent field; the system cannot assert unemployment from absence of data.

---

## GitHub README Recommendations

Structure the README in this order for maximum impact to a technical reviewer:

1. **One-line description** + a GIF of the dashboard in action (above the fold — the most important element).
2. **Problem statement** (2–3 sentences) — what problem does this solve and why is it hard.
3. **Key engineering decisions** (bulleted, 4–5 items) — the ones that show judgment, not just implementation:
   - Validated-only analytics invariant
   - "Employed vs Not Reported" semantics
   - Deterministic two-tier dedup (no AI)
   - Snapshot-based point-in-time reporting
   - JWT auth split from app-DB authorization
4. **Architecture diagram** (simple three-box: Next.js → FastAPI → Supabase) or a link to `docs/architecture/ER_DIAGRAM.md`.
5. **Tech stack table** — stack choices with brief rationale.
6. **Screenshots section** — 3–4 captioned screenshots (Overview, Career Outcomes, Directory, Curator Import).
7. **Local development** — copy the Quick Start block from the current README.
8. **Quality gates** — ruff ✅ · mypy strict ✅ · pytest 647 ✅ · vitest 23 ✅ · ESLint ✅ · TypeScript ✅ · build ✅.
9. **Scope / non-goals** — keep the "no AI/no LLM" list from the current README; it signals maturity.
10. **Live demo link** (add after P7.3/P7.5 are complete).

> **Most common README mistake:** burying the GIF below the fold. The decision of whether to read further is made in 5 seconds. Put the best GIF at the top, immediately after the one-line description.

---

## Interview Talking Points

Questions you are likely to be asked, and what to emphasize:

**"Why FastAPI over Django?"**
> FastAPI's async-native design fits the read-heavy, filter-heavy analytics workload. Pydantic gives us free request/response validation and auto-generates the OpenAPI schema. The dependency injection model makes RBAC enforcement clean and testable.

**"How does authentication work?"**
> Two-layer split: Supabase Auth handles authentication — it issues a JWT with the user's UUID. FastAPI verifies the JWT signature, then looks up the UUID in our application database to load the role and permissions. Permissions never come from the JWT — this means we can revoke or change permissions instantly without touching the token.

**"How do you handle data quality across three inconsistent sources?"**
> Five normalization steps at import time: program matching (handles 20+ name variants deterministically), company normalization (alias table, canonical entity), location normalization, industry classification at company level, and role/seniority classification. Every step is a pure function with exhaustive test coverage. The staging model means normalization failures never corrupt the main tables.

**"Why no AI/ML for deduplication?"**
> Explicit design decision. The faculty wanted to be able to explain every data point to accreditation bodies. If an alumnus is merged with another, the curator must have consciously decided that. AI matching introduces probabilistic decisions that can't be audited or explained. The deterministic two-tier approach is slower but fully accountable.

**"How do you handle the 'unemployment rate' question?"**
> We can't know if someone is unemployed — we only know if we have a current career record for them. Asserting an unemployment rate from absence of data would be epistemically wrong. So the API schema structurally omits `unemployment_rate`: the field does not exist in any response type. The label "Not Reported" is in the UI copy. This is enforced in the Pydantic schemas and tested in the test suite.
