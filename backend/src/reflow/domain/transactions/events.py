"""Domain events for the transactions context.

These are the facts that drive every other context. They live in the
`transaction-<id>` stream in the event store.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import ConfigDict, Field

from reflow.core.events.event import DomainEvent
from reflow.core.events.registry import register_event
from reflow.core.types import AttemptId, TransactionId
from reflow.domain.transactions.value_objects import (
    AttemptOutcome,
    CardMetadata,
    CurrencyCode,
    DeclineInfo,
)


class _TxnEvent(DomainEvent):
    """Common base for transaction-stream events."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    stream_type: ClassVar[str] = "transaction"

    transaction_id: TransactionId

    def stream_id(self) -> str:
        return f"transaction-{self.transaction_id}"


@register_event
class TransactionCreated(_TxnEvent):
    event_type: ClassVar[str] = "TransactionCreated"

    external_id: str = Field(description="Merchant's transaction id (idempotency key from merchant).")
    customer_ref: str | None = None
    amount_cents: int = Field(gt=0)
    currency: CurrencyCode
    card: CardMetadata
    gateway_provider: str
    gateway_account_ref: str | None = None


@register_event
class AttemptRecorded(_TxnEvent):
    """A charge attempt was made — could be initial or a retry."""

    event_type: ClassVar[str] = "AttemptRecorded"

    attempt_id: AttemptId
    attempt_number: int = Field(ge=1)
    gateway_provider: str
    gateway_request_id: str | None = None
    gateway_response_id: str | None = None
    outcome: AttemptOutcome
    decline: DeclineInfo | None = None
    latency_ms: int | None = Field(default=None, ge=0)


@register_event
class PaymentFailed(_TxnEvent):
    """The transaction has crossed into a 'failed' status — recovery candidate."""

    event_type: ClassVar[str] = "PaymentFailed"

    triggering_attempt_id: AttemptId
    decline: DeclineInfo


@register_event
class PaymentRecovered(_TxnEvent):
    """A recovery completed successfully. Terminal state for the txn aggregate."""

    event_type: ClassVar[str] = "PaymentRecovered"

    recovery_attempt_id: AttemptId
    recovered_amount_cents: int = Field(gt=0)


@register_event
class PaymentAbandoned(_TxnEvent):
    """We've given up — retry budget exhausted or policy denied permanently."""

    event_type: ClassVar[str] = "PaymentAbandoned"

    reason: str
