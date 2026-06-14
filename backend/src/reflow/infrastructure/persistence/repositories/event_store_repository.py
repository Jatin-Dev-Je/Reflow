"""Event store repository.

Responsibilities:
    * append_events()  — atomically write events + outbox rows with hash chain
                         and optimistic concurrency on UNIQUE(stream_id, version).
    * load_stream()    — read all (or post-snapshot) events for a stream.
    * save_snapshot()  — persist an aggregate snapshot.
    * load_latest_snapshot() — load the most recent snapshot for a stream.

The repository never commits; it uses the session it's given. Callers (use
cases) own the transaction boundary via `session_scope()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.events.event import DomainEvent, EventMetadata
from reflow.core.events.registry import get_event_class, upcast
from reflow.core.exceptions import ConcurrencyConflictError, DatabaseError
from reflow.core.observability.logging import get_logger
from reflow.core.security.signing import event_hash
from reflow.core.types import TenantId
from reflow.infrastructure.persistence.models.event_store import (
    EventModel,
    OutboxModel,
    SnapshotModel,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """The persisted form of an event — what comes back from the store."""

    id: str
    stream_id: str
    stream_type: str
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    metadata: dict[str, Any]
    previous_hash: str | None
    event_hash: str
    occurred_at: Any


@dataclass(frozen=True, slots=True)
class Snapshot:
    stream_id: str
    stream_type: str
    version: int
    state: dict[str, Any]
    schema_version: int


# -----------------------------------------------------------------------------
# Outbox destination routing — domain decides where events get fanned out.
# Centralised here so changing the routing topology is one edit.
# -----------------------------------------------------------------------------

def _outbox_destinations_for(event: DomainEvent) -> list[str]:
    """Return the stream(s) to publish this event to.

    Default: one destination per stream_type. Overridable per event by
    setting `event.stream_type` differently or adding a routing map.
    """
    return [f"redis-stream:{event.stream_type}"]


# -----------------------------------------------------------------------------
# Repository
# -----------------------------------------------------------------------------


class EventStoreRepository:
    """Append-only event store backed by Postgres.

    The repository does NOT manage transactions. Callers must wrap calls in
    `session_scope()` so a domain operation (commands + events + outbox) is
    written atomically.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---- Write -------------------------------------------------------------
    async def append_events(
        self,
        *,
        stream_id: str,
        expected_version: int,
        events: list[DomainEvent],
    ) -> list[StoredEvent]:
        """Append events to a stream.

        `expected_version` is the version of the *last* event the caller has
        seen. The first new event will be written at `expected_version + 1`.
        Pass `0` for a brand new stream.

        Raises:
            ConcurrencyConflictError: another writer beat us to (stream, version).
            DatabaseError: other DB failure.
        """
        if not events:
            return []

        # Load the last existing event for previous_hash linkage.
        previous_hash = await self._latest_hash(stream_id)
        if expected_version > 0 and previous_hash is None:
            # Caller claims version N>0 exists, but stream is empty — caller is wrong.
            raise ConcurrencyConflictError(
                f"Stream {stream_id!r} is empty but caller expected version {expected_version}",
                context={"stream_id": stream_id, "expected_version": expected_version},
            )

        stored: list[StoredEvent] = []
        current_version = expected_version
        current_prev_hash = previous_hash

        for event in events:
            current_version += 1
            payload = event.payload()
            metadata = event.metadata.model_dump_jsonable()
            new_hash = event_hash(
                previous_hash=current_prev_hash, payload=payload, metadata=metadata
            )

            row = EventModel(
                id=event.event_id,
                tenant_id=event.tenant_id,
                stream_id=stream_id,
                stream_type=event.stream_type,
                version=current_version,
                event_type=event.event_type,
                schema_version=event.schema_version,
                payload=payload,
                event_metadata=metadata,
                occurred_at=event.occurred_at,
                previous_hash=current_prev_hash,
                event_hash=new_hash,
            )
            self._session.add(row)

            # Outbox rows — same transaction, at-least-once fanout.
            for destination in _outbox_destinations_for(event):
                self._session.add(
                    OutboxModel(
                        event_id=event.event_id,
                        tenant_id=event.tenant_id,
                        destination=destination,
                    )
                )

            stored.append(
                StoredEvent(
                    id=str(event.event_id),
                    stream_id=stream_id,
                    stream_type=event.stream_type,
                    version=current_version,
                    event_type=event.event_type,
                    schema_version=event.schema_version,
                    payload=payload,
                    metadata=metadata,
                    previous_hash=current_prev_hash,
                    event_hash=new_hash,
                    occurred_at=event.occurred_at,
                )
            )
            current_prev_hash = new_hash

        try:
            await self._session.flush()
        except IntegrityError as exc:
            # UNIQUE(stream_id, version) violation = somebody else wrote first.
            if "events_stream_version_unique" in str(exc.orig) or "stream_id" in str(exc.orig):
                raise ConcurrencyConflictError(
                    f"Concurrent write to stream {stream_id!r} at version {current_version}",
                    context={
                        "stream_id": stream_id,
                        "expected_version": expected_version,
                        "attempted_version": current_version,
                    },
                ) from exc
            raise DatabaseError("Event append failed", context={"stream_id": stream_id}) from exc

        _logger.debug(
            "events.appended",
            stream_id=stream_id,
            count=len(events),
            first_version=expected_version + 1,
            last_version=current_version,
        )
        return stored

    # ---- Read --------------------------------------------------------------
    async def _latest_hash(self, stream_id: str) -> str | None:
        stmt = (
            select(EventModel.event_hash)
            .where(EventModel.stream_id == stream_id)
            .order_by(EventModel.version.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def load_stream(
        self,
        *,
        stream_id: str,
        from_version: int = 0,
    ) -> list[StoredEvent]:
        """Load events for a stream with `version > from_version`."""
        stmt = (
            select(EventModel)
            .where(EventModel.stream_id == stream_id)
            .where(EventModel.version > from_version)
            .order_by(EventModel.version.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            StoredEvent(
                id=str(r.id),
                stream_id=r.stream_id,
                stream_type=r.stream_type,
                version=r.version,
                event_type=r.event_type,
                schema_version=r.schema_version,
                payload=r.payload,
                metadata=r.event_metadata,
                previous_hash=r.previous_hash,
                event_hash=r.event_hash,
                occurred_at=r.occurred_at,
            )
            for r in rows
        ]

    async def materialize_stream(
        self,
        *,
        stream_id: str,
        tenant_id: TenantId,
        from_version: int = 0,
    ) -> list[DomainEvent]:
        """Load stream events and reconstruct them as typed DomainEvent objects.

        Unknown event types are skipped with a warning (forward-compat).
        Older schema_versions are upcasted via the registry.
        """
        stored = await self.load_stream(stream_id=stream_id, from_version=from_version)
        out: list[DomainEvent] = []
        for s in stored:
            target_cls = get_event_class(s.event_type, s.schema_version)
            current_payload = s.payload
            current_version = s.schema_version

            # Search forward for a known version to upcast to.
            if target_cls is None:
                next_version = current_version + 1
                while target_cls is None and next_version < 100:  # guard against runaway
                    target_cls = get_event_class(s.event_type, next_version)
                    if target_cls is None:
                        next_version += 1
                if target_cls is not None:
                    current_payload = upcast(
                        s.event_type, current_payload, current_version, next_version
                    )

            if target_cls is None:
                _logger.warning(
                    "events.unknown_type", event_type=s.event_type, schema_version=s.schema_version
                )
                continue

            try:
                event = target_cls(
                    event_id=s.id,  # type: ignore[arg-type]
                    tenant_id=tenant_id,
                    occurred_at=s.occurred_at,
                    metadata=EventMetadata(**s.metadata),
                    **current_payload,
                )
            except Exception as exc:
                _logger.error(
                    "events.materialize_failed",
                    event_type=s.event_type,
                    event_id=s.id,
                    error=str(exc),
                )
                raise DatabaseError(
                    f"Failed to materialize event {s.event_type} {s.id}", context={"event_id": s.id}
                ) from exc
            out.append(event)
        return out

    # ---- Snapshots ----------------------------------------------------------
    async def save_snapshot(
        self,
        *,
        stream_id: str,
        stream_type: str,
        tenant_id: TenantId,
        version: int,
        state: dict[str, Any],
        schema_version: int = 1,
    ) -> None:
        self._session.add(
            SnapshotModel(
                tenant_id=tenant_id,
                stream_id=stream_id,
                stream_type=stream_type,
                version=version,
                state=state,
                schema_version=schema_version,
            )
        )
        await self._session.flush()

    async def load_latest_snapshot(self, *, stream_id: str) -> Snapshot | None:
        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.stream_id == stream_id)
            .order_by(SnapshotModel.version.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Snapshot(
            stream_id=row.stream_id,
            stream_type=row.stream_type,
            version=row.version,
            state=row.state,
            schema_version=row.schema_version,
        )
