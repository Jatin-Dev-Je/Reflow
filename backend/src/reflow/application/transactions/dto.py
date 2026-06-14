"""Data transfer objects for the transactions application layer.

DTOs are the API of the use cases — they cross the layer boundary, so they
are strictly typed (Pydantic) and never reuse domain types directly that
would leak the domain through the wire.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import CommandId, TenantId, TransactionId
from reflow.domain.transactions import AttemptOutcome, CardMetadata, DeclineInfo


class IngestPaymentAttemptCommand(BaseModel):
    """Record a single charge attempt (initial or retry) for a transaction.

    If a transaction with the same (tenant_id, external_id) doesn't exist
    yet, it's created from `transaction_seed`. Otherwise it's loaded and the
    new attempt appended.
    """

    model_config = ConfigDict(extra="forbid")

    command_id: CommandId | None = Field(
        default=None,
        description="Idempotency key for the command. If supplied and an event "
        "with this command_id already exists, the command is a no-op.",
    )
    tenant_id: TenantId
    external_id: str = Field(min_length=1, max_length=256)

    # Required when creating; ignored when transaction already exists.
    transaction_seed: TransactionSeed

    outcome: AttemptOutcome
    decline: DeclineInfo | None = None
    gateway_request_id: str | None = None
    gateway_response_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class TransactionSeed(BaseModel):
    """Initial data for a transaction the first time we see it."""

    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0)
    currency: str
    card: CardMetadata
    gateway_provider: str
    gateway_account_ref: str | None = None
    customer_ref: str | None = None


class IngestPaymentAttemptResult(BaseModel):
    transaction_id: TransactionId
    attempt_id: str
    attempt_number: int
    status: str
    created_new_transaction: bool


# Order matters because `IngestPaymentAttemptCommand` references `TransactionSeed`.
IngestPaymentAttemptCommand.model_rebuild()
