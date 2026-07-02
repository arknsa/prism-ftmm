"""Health-check endpoint (Phase 0).

Reports liveness, the active app environment, and best-effort DB connectivity. The DB
check never fails the endpoint in Phase 0 — Supabase may not be provisioned yet.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.db import ping
from app.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_env: str
    database: str  # "connected" | "unconfigured" | "error"


@router.get("/health", response_model=HealthResponse, summary="Liveness & basic readiness")
def health() -> HealthResponse:
    settings = get_settings()

    database = "unconfigured"
    if settings.database_url:
        try:
            database = "connected" if ping() else "unconfigured"
        except Exception:  # pragma: no cover - depends on live DB
            logger.warning("health DB ping failed", extra={"event": "db_ping_failed"})
            database = "error"

    return HealthResponse(status="ok", app_env=settings.app_env, database=database)
