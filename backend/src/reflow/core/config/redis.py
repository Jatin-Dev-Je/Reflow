"""Redis connection settings.

We use three logical Redis databases to keep responsibilities clear:
    db 0 — application cache, distributed locks, kill-switch fanout
    db 1 — ARQ queue (BullMQ-equivalent for Python)
    db 2 — secondary cache (LLM prompt cache, decision cache)

Even when sharing a single Redis instance, separating logical DBs makes
`FLUSHDB` operations safe (e.g., we can flush the LLM cache without losing
queued jobs).
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    url: str = Field(default="redis://localhost:6379/0")
    queue_url: str = Field(default="redis://localhost:6379/1")
    cache_url: str = Field(default="redis://localhost:6379/2")

    max_connections: int = Field(default=50, ge=1, le=500)
    socket_timeout_seconds: float = Field(default=5.0, gt=0)
    socket_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    health_check_interval_seconds: int = Field(default=30, ge=1)

    # Channels for cross-process signals (Pub/Sub).
    killswitch_channel: str = Field(default="reflow:killswitch")
    policy_invalidation_channel: str = Field(default="reflow:policy:invalidate")
