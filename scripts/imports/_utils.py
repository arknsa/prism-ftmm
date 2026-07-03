"""Shared utilities for seed scripts.

Not part of the FastAPI application package. Importable only within scripts/imports/.
"""

from __future__ import annotations


def normalize_db_url(url: str) -> str:
    """Ensure the URL uses the postgresql+psycopg scheme required by SQLAlchemy v2 + psycopg v3."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
