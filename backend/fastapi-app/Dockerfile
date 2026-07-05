# syntax=docker/dockerfile:1
# Production image for the FTMM Alumni Intelligence Dashboard backend (Fly.io Machines).
# Uses the official uv image so the build/runtime toolchain matches local dev exactly.
# Deployment config only — no application code is modified.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# uv runtime behavior:
#   UV_COMPILE_BYTECODE  - precompile .pyc at install time -> faster cold starts.
#   UV_LINK_MODE=copy    - copy packages into the venv (no hardlink warnings in a container).
#   UV_PROJECT_ENVIRONMENT- pin the venv location so we can add it to PATH deterministically.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Install dependencies first, keyed only on the lockfiles, so this layer is cached
#    and re-run only when pyproject.toml / uv.lock change. --no-dev omits ruff/pytest/etc.
#    --frozen fails the build if uv.lock is out of date (reproducible installs).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 2) Copy the application source (app/, migrations/, alembic.ini, ...).
#    .dockerignore keeps .venv, caches, tests, and secrets out of the image.
COPY . .

# Uvicorn listens on the Fly internal_port. Fixed 8000 (see fly.toml internal_port).
EXPOSE 8000

# Start command (migrations are run separately via fly.toml release_command).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
