"""Root application settings.

Settings are sourced from environment variables and `.env` files.  The root
`Settings` object composes nested sub-settings (database, redis, llm, ...) so
each concern owns its own config surface.

A single `get_settings()` returns a cached singleton; tests can override it.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from reflow.core.config.database import DatabaseSettings
from reflow.core.config.llm import LLMKeys, LLMSettings
from reflow.core.config.observability import ObservabilitySettings
from reflow.core.config.redis import RedisSettings
from reflow.core.config.security import SecuritySettings


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Root settings — composed from sub-settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        env_prefix="APP_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    env: Environment = Field(default=Environment.DEVELOPMENT, alias="APP_ENV")
    name: str = Field(default="reflow-backend", alias="APP_NAME")
    host: str = Field(default="0.0.0.0", alias="APP_HOST")  # noqa: S104 — intentional, container-bound
    port: int = Field(default=8000, ge=1, le=65535, alias="APP_PORT")

    debug: bool = Field(default=False)
    api_prefix: str = Field(default="/api")
    cors_origins: tuple[str, ...] = Field(default=("http://localhost:3000",))

    # Sub-settings — each sources its own env block.
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    llm_keys: LLMKeys = Field(default_factory=LLMKeys)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.env == Environment.TEST


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Tests override via `app.dependency_overrides`."""
    return Settings()


def reset_settings_cache() -> None:
    """Invalidate the settings cache — useful in tests when env changes."""
    get_settings.cache_clear()
