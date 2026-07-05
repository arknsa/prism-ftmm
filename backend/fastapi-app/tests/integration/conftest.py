"""Fixtures for real-PostgreSQL integration tests.

The suite runs only when ``TEST_DATABASE_URL`` is set. That URL must point at a
Postgres *server* on which the connecting role may ``CREATE DATABASE`` (local
Postgres, GitHub Actions' ``postgres`` service, or a disposable Supabase/Postgres
project). Each session/test provisions a uniquely-named **ephemeral database**,
runs the real Alembic chain against it, and drops it on teardown.

Safety: every destructive operation (``downgrade base``, ``DROP DATABASE``) runs
ONLY against a throwaway database created here — never against the maintenance
database named in ``TEST_DATABASE_URL``.

No production code is modified. We reuse two read-only helpers from the app
(``app.db._normalize_url`` for driver normalization and ``app.config.get_settings``
so Alembic's ``env.py`` — which reads ``DATABASE_URL`` from settings — targets the
ephemeral database) and ``app.db.Base`` for metadata reflection.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.config import get_settings
from app.db import _normalize_url
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

_APP_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _APP_ROOT / "alembic.ini"
_MIGRATIONS_DIR = _APP_ROOT / "migrations"


def _server_url() -> URL | None:
    """Return the normalized maintenance-server URL, or None if unconfigured."""
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        return None
    return make_url(_normalize_url(raw))


@pytest.fixture(scope="session", autouse=True)
def _require_test_db() -> None:
    """Skip the entire integration package unless TEST_DATABASE_URL is set."""
    if _server_url() is None:
        pytest.skip("TEST_DATABASE_URL not set; skipping PostgreSQL integration tests")


# ---------------------------------------------------------------------------
# Alembic plumbing
# ---------------------------------------------------------------------------


def _make_alembic_config(db_url: str) -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    # Absolute script_location so the config is CWD-independent.
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@contextmanager
def _alembic_env(db_url: str) -> Iterator[None]:
    """Point env.py's settings at ``db_url`` for the duration of an Alembic command.

    env.py resolves the URL from ``get_settings().database_url``; we inject it via
    the environment and clear the settings cache, restoring both afterward so no
    other test is affected.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def script_heads() -> list[str]:
    """Return the head revision(s) declared by the migration scripts."""
    cfg = _make_alembic_config("postgresql+psycopg://unused/unused")
    return list(ScriptDirectory.from_config(cfg).get_heads())


# ---------------------------------------------------------------------------
# Ephemeral database lifecycle
# ---------------------------------------------------------------------------


@contextmanager
def _ephemeral_database() -> Iterator[URL]:
    """Create a uniquely-named database, yield its URL, and drop it afterward."""
    server = _server_url()
    assert server is not None  # guarded by _require_test_db
    db_name = f"prism_it_{uuid.uuid4().hex[:16]}"
    admin = create_engine(server, isolation_level="AUTOCOMMIT")
    try:
        try:
            with admin.connect() as conn:
                conn.exec_driver_sql(f'CREATE DATABASE "{db_name}"')
        except Exception as exc:  # e.g. role lacks CREATEDB (restricted Supabase)
            pytest.skip(
                "cannot CREATE DATABASE on the TEST_DATABASE_URL server "
                f"({type(exc).__name__}); point it at a Postgres where ephemeral "
                "test databases can be created"
            )
        try:
            yield server.set(database=db_name)
        finally:
            # WITH (FORCE) terminates any lingering sessions (PostgreSQL 13+).
            with admin.connect() as conn:
                conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
    finally:
        admin.dispose()


class MigrationHarness:
    """Runs Alembic up/down against one ephemeral database and inspects the result."""

    def __init__(self, url: URL) -> None:
        self.url = url
        self._url_str = url.render_as_string(hide_password=False)
        self._cfg = _make_alembic_config(self._url_str)

    def upgrade(self, revision: str = "head") -> None:
        with _alembic_env(self._url_str):
            command.upgrade(self._cfg, revision)

    def downgrade(self, revision: str) -> None:
        with _alembic_env(self._url_str):
            command.downgrade(self._cfg, revision)

    def current_revision(self) -> str | None:
        engine = create_engine(self.url)
        try:
            with engine.connect() as conn:
                if not inspect(conn).has_table("alembic_version"):
                    return None
                rows = conn.execute(text("SELECT version_num FROM alembic_version")).all()
                return rows[0][0] if rows else None
        finally:
            engine.dispose()

    def table_names(self) -> set[str]:
        engine = create_engine(self.url)
        try:
            return set(inspect(engine).get_table_names())
        finally:
            engine.dispose()


@pytest.fixture()
def migration_harness() -> Iterator[MigrationHarness]:
    """Yield a MigrationHarness bound to a fresh, empty ephemeral database."""
    with _ephemeral_database() as url:
        yield MigrationHarness(url)


@pytest.fixture()
def engine(migration_harness: MigrationHarness) -> Iterator[Engine]:
    """A fresh ephemeral database migrated to head, exposed as an Engine.

    Shared by the row-level integration test files (constraints, RBAC, …) so each
    does not redefine it. Behavior is identical to the original per-file fixture.
    """
    migration_harness.upgrade("head")
    eng = create_engine(migration_harness.url)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture(scope="session")
def alembic_heads() -> list[str]:
    """The migration script head(s) — should be exactly one."""
    return script_heads()


@pytest.fixture(scope="session")
def revision_count() -> int:
    """Number of revisions in the chain (steps from head down to base)."""
    cfg = _make_alembic_config("postgresql+psycopg://unused/unused")
    return sum(1 for _ in ScriptDirectory.from_config(cfg).walk_revisions())
