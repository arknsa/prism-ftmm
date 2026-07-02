"""SQLAlchemy engine/session wiring for the Supabase Postgres pooler.

Phase 0 has **no models** — this only establishes connectivity and the migration target.
The engine is created lazily so the app can boot in environments without ``DATABASE_URL``
(e.g. a bare health check before Supabase is provisioned).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base. Models are added from Phase 1 onward."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _normalize_url(url: str) -> str:
    """Ensure SQLAlchemy uses the psycopg (v3) driver for Postgres URLs."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    """Return a process-wide engine bound to the Supabase pooler, creating it on first use."""
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Provide the Supabase pooler URI before using the DB."
            )
        # pool_pre_ping guards against stale pooled connections (PgBouncer/Supabase pooler).
        _engine = create_engine(
            _normalize_url(settings.database_url),
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a SQLAlchemy session (used from Phase 1 onward)."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping() -> bool:
    """Execute ``SELECT 1`` to confirm DB connectivity. Returns False if DB is unconfigured."""
    settings = get_settings()
    if not settings.database_url:
        return False
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
