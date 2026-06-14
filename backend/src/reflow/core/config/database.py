"""Database settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Postgres connection + pooling.

    The URL must use the +asyncpg dialect: postgresql+asyncpg://...
    """

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = Field(
        default="postgresql+asyncpg://reflow:reflow@localhost:5432/reflow",
        description="SQLAlchemy URL using the asyncpg driver.",
    )
    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=200)
    pool_timeout_seconds: float = Field(default=30.0, gt=0)
    pool_recycle_seconds: int = Field(
        default=1800,
        description="Recycle connections every N seconds; mitigates idle-disconnect on hosted Postgres.",
    )
    echo: bool = Field(default=False, description="Verbose SQL logging — dev only.")
    statement_timeout_ms: int = Field(
        default=30_000,
        description="Server-side statement timeout, applied via SET on each connection.",
    )
