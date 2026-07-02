"""FastAPI application factory.

This is the single business-logic gateway (D-031). The frontend never touches the database
directly; all access flows through this app. Phase 0 exposes only ``/health``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import Settings, get_settings
from app.logging import configure_logging, get_logger


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    configure_logging()
    logger = get_logger(__name__)

    app = FastAPI(
        title=settings.app_name,
        version="0.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)

    logger.info(
        "application initialized",
        extra={"event": "app_init", "app_env": settings.app_env},
    )
    return app


app = create_app()
