"""Domain event base.

Every domain event is a frozen Pydantic model with:
    * `event_type`   — discriminator (class name by default)
    * `schema_version` — incremented on payload shape change; upcasters bridge
    * `payload`      — domain-specific data (sub-models)
    * `metadata`     — causation/correlation/command/actor IDs

`payload` and `metadata` are serialized to JSONB at the persistence boundary.
The class itself never touches the database — repositories do.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import (
    CausationId,
    CommandId,
    CorrelationId,
    EventId,
    TenantId,
    new_event_id,
)


class EventMetadata(BaseModel):
    """Causation / correlation / actor context attached to every event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    command_id: CommandId | None = None
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    actor_id: UUID | None = None       # user_id or system actor
    actor_type: str | None = None      # "user", "system", "webhook", "scheduler"
    source: str | None = None          # e.g. "webhook:stripe", "worker:recovery"
    trace_id: str | None = None
    span_id: str | None = None

    def model_dump_jsonable(self) -> dict[str, Any]:
        # mode='json' converts UUIDs to strings for JSONB storage.
        return self.model_dump(mode="json", exclude_none=True)


class DomainEvent(BaseModel):
    """Base class for every domain event.

    Subclasses MUST declare `stream_type: ClassVar[str]` and override
    `stream_id(self)` to return the aggregate stream identifier.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Class-level discriminator. Subclasses override:
    stream_type: ClassVar[str] = "abstract"
    event_type: ClassVar[str] = "DomainEvent"
    schema_version: ClassVar[int] = 1

    event_id: EventId = Field(default_factory=new_event_id)
    tenant_id: TenantId
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    # ---- Subclass contract --------------------------------------------------
    def stream_id(self) -> str:
        """Return the stream identifier — typically '<type>-<aggregate_id>'."""
        raise NotImplementedError("DomainEvent subclasses must implement stream_id()")

    def payload(self) -> dict[str, Any]:
        """Return the JSON-serializable payload (everything except envelope)."""
        excluded = {"event_id", "tenant_id", "occurred_at", "metadata"}
        return self.model_dump(mode="json", exclude=excluded)
