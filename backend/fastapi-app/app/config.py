"""Application settings, loaded from the environment via pydantic-settings.

Secrets are provided per platform (Railway / Vercel / Supabase) per D-035 and are never
committed. See ``backend/.env.example`` for the catalogue of keys (no values).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "production"]


class Settings(BaseSettings):
    """Typed application configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime ---
    app_env: AppEnv = Field(default="local", alias="APP_ENV")
    app_name: str = "FTMM Alumni Intelligence Dashboard API"

    # --- CORS: comma-separated list of allowed origins (Vercel URL in prod) ---
    backend_cors_origins: list[str] = Field(default_factory=list, alias="BACKEND_CORS_ORIGINS")

    # --- Database: Supabase Postgres pooler URI. Optional in Phase 0 so the app
    #     can boot without a DB; later phases require it. ---
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # --- Supabase (consumed from Phase 2 onward; declared now so env is complete) ---
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str | None = Field(default=None, alias="SUPABASE_JWT_SECRET")

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept either a JSON list or a comma-separated string for CORS origins."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value  # let pydantic parse JSON
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one read of the environment per process)."""
    return Settings()
