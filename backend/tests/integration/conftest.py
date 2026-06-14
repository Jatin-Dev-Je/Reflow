"""Integration test fixtures — spin up real Postgres + Redis via testcontainers.

Containers are scoped to the session: one Postgres + one Redis for the whole
suite, schema applied once. Each test gets its own session within a savepoint
that rolls back at the end, so tests are isolated without container restarts.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "migrations" / "sql" / "001_initial_schema.sql"


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    """Start one Postgres container for the whole test session."""
    container = (
        PostgresContainer(image="pgvector/pgvector:pg16", dbname="reflow_test")
        .with_env("POSTGRES_INITDB_ARGS", "--encoding=UTF8 --locale=C")
    )
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    container = RedisContainer(image="redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    sync_url = postgres_container.get_connection_url()
    # testcontainers returns a psycopg2 URL; we want asyncpg.
    return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
def redis_url(redis_container: RedisContainer) -> str:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest_asyncio.fixture(scope="session")
async def _engine_with_schema(database_url: str):
    """Create a session-scoped engine and apply the schema once."""
    # Push the URL into env so `get_settings()` picks it up if some code uses it.
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # not used directly here
    # Clear cached settings so the override sticks.
    from reflow.core.config import reset_settings_cache

    reset_settings_cache()

    engine = create_async_engine(database_url, future=True)

    # Apply schema. The DDL is split by `;` — execute statement-by-statement to
    # handle DO blocks and CREATE TRIGGER correctly via `text()`.
    from sqlalchemy import text

    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    async with engine.begin() as conn:
        await conn.execute(text(sql))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_engine_with_schema) -> AsyncIterator[AsyncSession]:
    """One session per test, wrapped in a transaction that always rolls back."""
    sessionmaker = async_sessionmaker(_engine_with_schema, expire_on_commit=False)
    async with sessionmaker() as session:
        # We don't begin a savepoint here because event_store tests need real
        # commits to verify constraints. Each test cleans up after itself.
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def clean_event_store(db_session: AsyncSession) -> AsyncSession:
    """Truncate event-store tables so tests start from a known state."""
    from sqlalchemy import text

    await db_session.execute(
        text(
            "TRUNCATE audit.outbox, audit.snapshots, audit.events RESTART IDENTITY CASCADE"
        )
    )
    await db_session.commit()
    return db_session
