"""HTTP schemas for transactions endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from reflow.domain.transactions import (
    AttemptOutcome,
    CardMetadata,
    DeclineCategory,
    TransactionStatus,
)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    external_id: str
    customer_ref: str | None = None
    amount_cents: int
    currency: str
    card: CardMetadata
    gateway_id: str
    issuer_id: str | None = None
    status: TransactionStatus
    initial_failed_at: datetime | None = None
    final_resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    attempt_number: int
    gateway_id: str
    outcome: AttemptOutcome
    decline_code: str | None = None
    decline_code_normalized: str | None = None
    decline_category: DeclineCategory | None = None
    decline_message: str | None = None
    latency_ms: int | None = None
    attempted_at: datetime


class TransactionsPage(BaseModel):
    items: list[TransactionRead]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page. Pass back via `cursor` query param.",
    )


class TimelineEntry(BaseModel):
    """One row in the Trust View timeline."""

    occurred_at: datetime
    event_type: str
    summary: str
    payload: dict


class TransactionStats(BaseModel):
    """Aggregate stats for the transactions context over a window."""

    model_config = ConfigDict(extra="forbid")

    window_days: int = Field(gt=0)
    total: int = Field(ge=0)
    total_amount_cents: int = Field(ge=0)
    by_status: dict[str, int]
    by_gateway: dict[str, int]
    avg_amount_cents: int = Field(ge=0)


class RecoveryStats(BaseModel):
    """Aggregate stats for the recovery context over a window."""

    model_config = ConfigDict(extra="forbid")

    window_days: int = Field(gt=0)
    total: int = Field(ge=0)
    by_state: dict[str, int]
    by_outcome: dict[str, int]
    recovery_rate: float = Field(ge=0, le=1)
    avg_recovery_latency_ms: int | None = None
    total_recovered_cents: int = Field(ge=0)
