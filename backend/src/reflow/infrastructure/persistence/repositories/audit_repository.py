"""Read-only audit queries.

The audit context is the only place that reads `audit.events` for display
purposes. Everywhere else, code goes through the EventStoreRepository for
append + materialize. Keeping audit queries here means a security review only
has to look at one place to verify what's exposed.

Bounded by tenant_id everywhere — multi-tenant safety is enforced before any
row leaves this repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.exceptions import DomainError
from reflow.core.types import EventId, TenantId
from reflow.infrastructure.persistence.models import ChainAnchorModel, EventModel

# Hard cap on any audit query to prevent abuse / accidental DoS.
MAX_PAGE_SIZE = 500


@dataclass(frozen=True, slots=True)
class AuditEventView:
    """The shape we return to the API — never the ORM row directly."""

    id: UUID
    global_sequence: int
    tenant_id: UUID
    stream_id: str
    stream_type: str
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    metadata: dict[str, Any]
    occurred_at: datetime
    recorded_at: datetime
    previous_hash: str | None
    event_hash: str


@dataclass(frozen=True, slots=True)
class ChainAnchorView:
    id: UUID
    tenant_id: UUID | None
    start_sequence: int
    end_sequence: int
    event_count: int
    merkle_root: str
    signature: str
    signer_key_id: str
    signed_at: datetime


def _to_event_view(row: EventModel) -> AuditEventView:
    return AuditEventView(
        id=row.id,
        global_sequence=row.global_sequence,
        tenant_id=row.tenant_id,
        stream_id=row.stream_id,
        stream_type=row.stream_type,
        version=row.version,
        event_type=row.event_type,
        schema_version=row.schema_version,
        payload=row.payload,
        metadata=row.event_metadata,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        previous_hash=row.previous_hash,
        event_hash=row.event_hash,
    )


def _to_anchor_view(row: ChainAnchorModel) -> ChainAnchorView:
    return ChainAnchorView(
        id=row.id,
        tenant_id=row.tenant_id,
        start_sequence=row.start_sequence,
        end_sequence=row.end_sequence,
        event_count=row.event_count,
        merkle_root=row.merkle_root,
        signature=row.signature,
        signer_key_id=row.signer_key_id,
        signed_at=row.signed_at,
    )


class AuditRepository:
    """Read-only queries over the audit schema, tenant-scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_events(
        self,
        *,
        tenant_id: TenantId,
        stream_type: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[AuditEventView]:
        limit = min(limit, MAX_PAGE_SIZE)
        stmt = (
            select(EventModel)
            .where(EventModel.tenant_id == tenant_id)
            .order_by(EventModel.global_sequence.desc())
            .limit(limit)
        )
        if stream_type is not None:
            stmt = stmt.where(EventModel.stream_type == stream_type)
        if event_type is not None:
            stmt = stmt.where(EventModel.event_type == event_type)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_event_view(r) for r in rows]

    async def get_event(
        self, *, tenant_id: TenantId, event_id: EventId
    ) -> AuditEventView:
        row = await self._session.get(EventModel, event_id)
        if row is None:
            raise DomainError(
                f"Event {event_id} not found", context={"event_id": str(event_id)}
            )
        # Tenant-isolation check — never leak across tenants.
        if row.tenant_id != tenant_id:
            raise DomainError(
                f"Event {event_id} not found", context={"event_id": str(event_id)}
            )
        return _to_event_view(row)

    async def list_stream_events(
        self, *, tenant_id: TenantId, stream_id: str, limit: int = 200
    ) -> list[AuditEventView]:
        limit = min(limit, MAX_PAGE_SIZE)
        stmt = (
            select(EventModel)
            .where(EventModel.tenant_id == tenant_id)
            .where(EventModel.stream_id == stream_id)
            .order_by(EventModel.version.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_event_view(r) for r in rows]

    async def list_anchors(self, *, limit: int = 50) -> list[ChainAnchorView]:
        """Anchors are global (or per-tenant if scoped). For now we expose only globals."""
        limit = min(limit, MAX_PAGE_SIZE)
        stmt = (
            select(ChainAnchorModel)
            .order_by(ChainAnchorModel.signed_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_anchor_view(r) for r in rows]

    async def latest_anchor(self) -> ChainAnchorView | None:
        stmt = (
            select(ChainAnchorModel)
            .order_by(ChainAnchorModel.signed_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_anchor_view(row) if row else None
