# Database migrations

The **canonical** Alembic migration tree lives under
[`backend/fastapi-app/migrations/`](../../backend/fastapi-app/migrations/).

This directory exists so the `database/` epic from the monorepo layout (D-037) stays
discoverable. Do not add migration files here — run Alembic from `backend/fastapi-app/`:

```bash
cd backend/fastapi-app
uv run alembic upgrade head
```
