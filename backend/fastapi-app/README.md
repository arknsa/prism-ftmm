# Backend — FastAPI

Single business-logic gateway (D-031) for the FTMM Alumni Intelligence Dashboard. Phase 0
exposes only `GET /health`. No models yet.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup & run

```bash
cd backend/fastapi-app
uv sync                 # install runtime + dev deps
cp .env.example .env    # fill in values (APP_ENV=local is enough to boot)

uv run uvicorn app.main:app --reload --port 8000
# -> http://localhost:8000/health
# -> http://localhost:8000/docs
```

## Quality gates

```bash
uv run ruff check app tests
uv run black --check app tests
uv run mypy app
uv run pytest
```

## Migrations (Alembic)

The DB URL is read from `DATABASE_URL` (Supabase **pooler**) at runtime — never stored in
`alembic.ini`. Phase 0 ships one **empty baseline** migration.

```bash
uv run alembic upgrade head     # applies the empty baseline (requires DATABASE_URL)
uv run alembic revision -m "msg"   # create a new migration (Phase 1+)
```

The canonical migration tree is `migrations/`; `database/migrations/` at the repo root is a
pointer only.

## Env vars

See [.env.example](.env.example). Values are provided per platform (Railway) per D-035.
