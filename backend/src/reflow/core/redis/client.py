"""Async Redis clients (three logical databases — cache, queue, secondary).

Each module needing Redis grabs the appropriate client via the dependency
provided by `api/deps.py` rather than constructing its own connection pool.
"""

from __future__ import annotations

from typing import cast

from redis.asyncio import Redis, from_url

from reflow.core.config import RedisSettings, get_settings
from reflow.core.exceptions import CacheError
from reflow.core.observability.logging import get_logger

_logger = get_logger(__name__)

_clients: dict[str, Redis] = {}


def _build(url: str, settings: RedisSettings) -> Redis:
    return cast(
        Redis,
        from_url(
            url,
            encoding="utf-8",
            decode_responses=False,  # binary-safe — let callers decode explicitly
            max_connections=settings.max_connections,
            socket_timeout=settings.socket_timeout_seconds,
            socket_connect_timeout=settings.socket_connect_timeout_seconds,
            health_check_interval=settings.health_check_interval_seconds,
            retry_on_timeout=True,
        ),
    )


def get_redis(*, role: str = "cache") -> Redis:
    """Get the cached client for a logical role: 'cache' | 'queue' | 'secondary'."""
    if role in _clients:
        return _clients[role]

    settings = get_settings().redis
    url = {"cache": settings.url, "queue": settings.queue_url, "secondary": settings.cache_url}.get(role)
    if url is None:
        raise CacheError(f"Unknown redis role: {role!r}")

    client = _build(url, settings)
    _clients[role] = client
    _logger.info("redis.client.initialized", role=role)
    return client


async def close_redis_clients() -> None:
    """Close every cached client. Call at shutdown."""
    for role, client in list(_clients.items()):
        try:
            await client.aclose()
        except Exception as exc:  # noqa: BLE001 — log + continue on shutdown
            _logger.warning("redis.client.close_failed", role=role, error=str(exc))
    _clients.clear()


async def ping_redis(role: str = "cache") -> bool:
    """Health-check the given Redis role."""
    try:
        return bool(await get_redis(role=role).ping())
    except Exception as exc:  # noqa: BLE001
        _logger.warning("redis.ping.failed", role=role, error=str(exc))
        return False
