"""FastAPI application factory.

This is the single business-logic gateway (D-031). The frontend never touches the database
directly; all access flows through this app.

Routers registered per phase:
  Phase 0: /health
  Phase 2: /auth (register, login, me), /me, /users
  Phase 3: /api/v1/imports
  Phase 4: /api/v1/dedup, /api/v1/snapshots, /api/v1/commit, /api/v1/companies
  Phase 5: /api/v1/analytics/* (filter-options, overview, career-outcomes, companies,
            industries, geography, directory, alumni/{id})
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.commit import router as commit_router
from app.api.company import router as company_router
from app.api.dedup import router as dedup_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.me import router as me_router
from app.api.snapshots import router as snapshots_router
from app.api.users import router as users_router
from app.config import Settings, get_settings
from app.logging import configure_logging, get_logger

# Configuration that must be present when APP_ENV=production. Missing values fail
# fast at startup instead of surfacing later as opaque 500/503s.
_REQUIRED_IN_PRODUCTION: tuple[str, ...] = ("database_url", "supabase_url")
_RECOMMENDED_IN_PRODUCTION: tuple[str, ...] = (
    "supabase_service_role_key",
    "supabase_anon_key",
)


def _validate_production_config(settings: Settings, logger: logging.Logger) -> None:
    """Fail fast on missing critical production configuration (deployment safety).

    Runs only when APP_ENV=production, so local and test boots are unaffected.
    Does not change any application behavior — it only guards startup.
    """
    missing = [name.upper() for name in _REQUIRED_IN_PRODUCTION if not getattr(settings, name)]
    if missing:
        raise RuntimeError("Missing required production configuration: " + ", ".join(missing))
    if not settings.backend_cors_origins:
        logger.warning(
            "BACKEND_CORS_ORIGINS is empty in production; browser requests from the "
            "frontend will be blocked by CORS."
        )
    for name in _RECOMMENDED_IN_PRODUCTION:
        if not getattr(settings, name):
            logger.warning(
                "%s is not set; admin / user-provisioning endpoints will return 503.",
                name.upper(),
            )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    configure_logging(level=settings.log_level)
    logger = get_logger(__name__)

    if settings.is_production:
        _validate_production_config(settings, logger)

    # Disable interactive docs in production — the full schema is still exported
    # offline via `uv run python -c "import app.main; ..."` for tooling consumers.
    _docs_url = None if settings.is_production else "/docs"
    _openapi_url = None if settings.is_production else "/openapi.json"

    app = FastAPI(
        title=settings.app_name,
        version="0.0.0",
        docs_url=_docs_url,
        openapi_url=_openapi_url,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(users_router)
    app.include_router(imports_router)
    app.include_router(dedup_router)
    app.include_router(snapshots_router)
    app.include_router(commit_router)
    app.include_router(company_router)
    app.include_router(analytics_router)

    logger.info(
        "application initialized",
        extra={"event": "app_init", "app_env": settings.app_env},
    )
    return app


app = create_app()
