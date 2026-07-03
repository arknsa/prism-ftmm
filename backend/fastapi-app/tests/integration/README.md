# Integration tests (real PostgreSQL)

These tests run the **real** Alembic migration chain and schema against a live
PostgreSQL server. They are **skipped automatically** unless `TEST_DATABASE_URL`
is set, so the default `pytest` run (unit tests) is unaffected everywhere.

`TEST_DATABASE_URL` must point at a Postgres **server** whose role may
`CREATE DATABASE`. Each test provisions its own uniquely-named ephemeral database,
runs the migrations, and drops it afterward — the maintenance database named in
the URL is never modified.

## Run locally

Any disposable Postgres works (local install, or a throwaway Docker container):

```bash
# Option A — Docker (one-off, matches production PG 17)
docker run -d --name pg-it -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:17

# Point the suite at it and run only the integration tests
export TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:55432/postgres"
uv run pytest -m integration -q

# Tear down
docker rm -f pg-it
```

The URL may be `postgresql://…` or `postgresql+psycopg://…`; it is normalized to
the psycopg 3 driver automatically.

- Run only integration tests: `uv run pytest -m integration`
- Run everything except integration: `uv run pytest -m "not integration"`
- Default run (no `TEST_DATABASE_URL`): integration tests report as *skipped*.

## Supabase

Point `TEST_DATABASE_URL` at a **disposable** Supabase/Postgres whose role has
`CREATE DATABASE` (e.g. a dedicated test project via its direct connection). The
suite never runs destructive migrations against the database named in the URL —
only against the ephemeral databases it creates. Do **not** point this at a
production project.

## GitHub Actions

```yaml
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 5
    env:
      TEST_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv run pytest -m integration -q
        working-directory: backend/fastapi-app
```

The standard unit-test job needs no database and can run `uv run pytest -m "not integration"`.
