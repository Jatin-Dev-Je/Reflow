"""Outbox relay — publishes audit.outbox rows to Redis Streams.

The relay implements the **transactional outbox** pattern. Events are written
into Postgres in the same transaction as the aggregate state changes, so we
never have the dual-write problem. The relay polls the outbox table, publishes
each row to a Redis Stream, and marks the row delivered.

Properties:
    * **At-least-once delivery** — consumers must be idempotent on event_id.
    * **Leader-elected**: only one relay instance publishes at a time, via a
      Postgres advisory lock (deadlock-free, auto-released on disconnect).
    * **Bounded batching**: pulls N rows per tick, processes, sleeps.
    * **Exponential backoff with jitter** on per-row failures.
    * **Dead-letter** after MAX_ATTEMPTS — surfaces in the ops dashboard.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

import orjson
from redis.asyncio import Redis
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.database import session_scope
from reflow.core.observability.logging import get_logger
from reflow.core.redis import get_redis
from reflow.infrastructure.persistence.models import EventModel, OutboxModel

_logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Knobs
# -----------------------------------------------------------------------------

BATCH_SIZE: Final[int] = 100
POLL_INTERVAL_SECONDS: Final[float] = 0.5
MAX_ATTEMPTS: Final[int] = 5
BACKOFF_BASE_SECONDS: Final[float] = 1.0
BACKOFF_JITTER_FRACTION: Final[float] = 0.25
# Postgres advisory-lock key (any int64). Keep this stable across releases.
ADVISORY_LOCK_KEY: Final[int] = 0x_5EF10_0017_B0BA  # arbitrary, stable int64 key

# Stream cap — Redis trims oldest entries beyond this point.
STREAM_MAXLEN_APPROX: Final[int] = 100_000


# -----------------------------------------------------------------------------
# Stream helpers
# -----------------------------------------------------------------------------


def _parse_destination(destination: str) -> tuple[str, str]:
    """Parse 'redis-stream:<name>' -> ('redis-stream', '<name>')."""
    kind, _, name = destination.partition(":")
    return kind, name


async def _publish_to_stream(
    redis: Redis, *, stream: str, event_row: EventModel
) -> str:
    """XADD the event payload to the named Redis Stream. Returns the stream id."""
    fields = {
        "event_id": str(event_row.id),
        "tenant_id": str(event_row.tenant_id),
        "stream_id": event_row.stream_id,
        "stream_type": event_row.stream_type,
        "version": str(event_row.version),
        "event_type": event_row.event_type,
        "schema_version": str(event_row.schema_version),
        "occurred_at": event_row.occurred_at.isoformat(),
        "event_hash": event_row.event_hash,
        "payload": orjson.dumps(event_row.payload).decode(),
        "metadata": orjson.dumps(event_row.event_metadata).decode(),
    }
    return (
        await redis.xadd(
            name=stream,
            fields=fields,
            maxlen=STREAM_MAXLEN_APPROX,
            approximate=True,
        )
    ).decode()


# -----------------------------------------------------------------------------
# Advisory lock — only one relay instance publishes at a time
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class _LeaderToken:
    held: bool


async def _try_acquire_leader(session: AsyncSession) -> _LeaderToken:
    """Non-blocking advisory lock. Returns held=True only if we got it."""
    row = await session.execute(
        text("SELECT pg_try_advisory_lock(:k) AS got"), {"k": ADVISORY_LOCK_KEY}
    )
    return _LeaderToken(held=bool(row.scalar()))


async def _release_leader(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY}
    )


# -----------------------------------------------------------------------------
# Core relay loop
# -----------------------------------------------------------------------------


def _backoff_until(attempts: int) -> datetime:
    """Exponential backoff with jitter — never below 1s, capped near 5 min."""
    base = min(BACKOFF_BASE_SECONDS * (2**attempts), 300.0)
    jitter = random.uniform(-BACKOFF_JITTER_FRACTION, BACKOFF_JITTER_FRACTION) * base
    return datetime.now(UTC) + timedelta(seconds=max(1.0, base + jitter))


async def relay_once(
    *,
    session: AsyncSession,
    redis: Redis,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Process one batch of pending outbox rows. Returns how many were delivered."""
    stmt = (
        select(OutboxModel, EventModel)
        .join(EventModel, OutboxModel.event_id == EventModel.id)
        .where(OutboxModel.status == "pending")
        .where(OutboxModel.next_attempt_at <= datetime.now(UTC))
        .order_by(OutboxModel.next_attempt_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return 0

    delivered = 0
    for outbox_row, event_row in rows:
        kind, stream = _parse_destination(outbox_row.destination)
        if kind != "redis-stream":
            _logger.warning(
                "outbox.unsupported_destination",
                outbox_id=str(outbox_row.id),
                destination=outbox_row.destination,
            )
            await _mark_failed(session, outbox_row, "unsupported_destination", terminal=True)
            continue

        try:
            await _publish_to_stream(redis, stream=stream, event_row=event_row)
        except Exception as exc:  # noqa: BLE001 — relay must keep going
            attempts = outbox_row.attempts + 1
            if attempts >= MAX_ATTEMPTS:
                await _mark_failed(session, outbox_row, str(exc), terminal=True)
                _logger.error(
                    "outbox.dead_letter",
                    outbox_id=str(outbox_row.id),
                    event_id=str(outbox_row.event_id),
                    error=str(exc),
                )
            else:
                next_at = _backoff_until(attempts)
                await session.execute(
                    update(OutboxModel)
                    .where(OutboxModel.id == outbox_row.id)
                    .values(
                        attempts=attempts,
                        next_attempt_at=next_at,
                        last_error=str(exc)[:512],
                    )
                )
                _logger.warning(
                    "outbox.retry_scheduled",
                    outbox_id=str(outbox_row.id),
                    attempts=attempts,
                    next_attempt_at=next_at.isoformat(),
                )
            continue

        await session.execute(
            update(OutboxModel)
            .where(OutboxModel.id == outbox_row.id)
            .values(
                status="delivered",
                delivered_at=datetime.now(UTC),
                attempts=outbox_row.attempts + 1,
                last_error=None,
            )
        )
        delivered += 1

    await session.commit()
    return delivered


async def _mark_failed(
    session: AsyncSession,
    row: OutboxModel,
    error: str,
    *,
    terminal: bool,
) -> None:
    await session.execute(
        update(OutboxModel)
        .where(OutboxModel.id == row.id)
        .values(
            status="dead" if terminal else "failed",
            attempts=row.attempts + 1,
            last_error=error[:512],
        )
    )


# -----------------------------------------------------------------------------
# Worker entrypoint
# -----------------------------------------------------------------------------


async def run_relay_forever(*, poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Run the relay loop until cancelled.

    Acquires the leader lock; non-leader instances poll for the lock at the
    same cadence so failover is quick.
    """
    redis = get_redis(role="cache")
    _logger.info("outbox.relay.starting")
    while True:
        try:
            async with session_scope() as session:
                token = await _try_acquire_leader(session)
                if not token.held:
                    await session.commit()
                    await asyncio.sleep(poll_interval)
                    continue
                try:
                    while True:
                        delivered = await relay_once(session=session, redis=redis)
                        if delivered == 0:
                            await asyncio.sleep(poll_interval)
                finally:
                    await _release_leader(session)
        except asyncio.CancelledError:
            _logger.info("outbox.relay.cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 — retry on any failure
            _logger.error("outbox.relay.error", error=str(exc))
            await asyncio.sleep(poll_interval * 4)
