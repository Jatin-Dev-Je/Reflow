"""Async SQLAlchemy engine + session factory.

Single engine per process.  Each request/job/handler gets its own short-lived
`AsyncSession` via `session_scope()`.  Commit-on-success, rollback-on-error
behaviour is enforced by the context manager so callers cannot forget.

Statement timeout is enforced server-side per connection — a defensive guard
against runaway queries blocking the connection pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from reflow.core.config import DatabaseSettings, get_settings
from reflow.core.observability.logging import get_logger

_logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _attach_engine_listeners(engine: AsyncEngine, settings: DatabaseSettings) -> None:
    """Set statement timeout server-side for every connection in the pool."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_timeouts(dbapi_conn: Any, _: Any) -> None:
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")
            cur.execute("SET idle_in_transaction_session_timeout = 60000")
        finally:
            cur.close()


def init_engine(settings: DatabaseSettings | None = None) -> AsyncEngine:
    """Create the singleton engine. Idempotent."""
    global _engine, _sessionmaker
    if _engine is not None:
        return _engine

    settings = settings or get_settings().database

    _engine = create_async_engine(
        settings.url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
        pool_recycle=settings.pool_recycle_seconds,
        pool_pre_ping=True,
        echo=settings.echo,
        future=True,
    )
    _attach_engine_listeners(_engine, settings)

    _sessionmaker = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    _logger.info("database.engine.initialized", url=settings.url.split("@")[-1])
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        return init_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None  # noqa: S101 — invariant after init
    return _sessionmaker


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open a session, commit on success, rollback on error.

    Usage:
        async with session_scope() as session:
            await session.execute(...)
    """
    sm = get_sessionmaker()
    session = sm()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Tear down the engine. Call at process shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
        _logger.info("database.engine.disposed")
