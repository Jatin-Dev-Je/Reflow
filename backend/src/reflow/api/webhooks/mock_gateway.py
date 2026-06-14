"""Mock-gateway webhook.

The simulator + dev tooling POST here to inject synthetic transaction events.
No signature verification — this endpoint is for internal use only and is
disabled in production via `flags.gateway.mock.enabled`.

In production the real Stripe / Adyen / Braintree webhooks live alongside this
in `api/webhooks/`; they implement provider-specific signature verification.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.application.transactions import (
    IngestPaymentAttemptCommand,
    IngestPaymentAttemptHandler,
    IngestPaymentAttemptResult,
    TransactionSeed,
)
from reflow.core.types import new_command_id
from reflow.domain.transactions import (
    AttemptOutcome,
    CardMetadata,
    DeclineInfo,
)
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/webhooks/mock-gateway", tags=["webhooks"])


class MockGatewayPayload(BaseModel):
    """Body schema for the mock-gateway webhook."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=256)
    amount_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    card: CardMetadata
    gateway_provider: str = "mock"
    gateway_account_ref: str | None = None
    customer_ref: str | None = None
    outcome: AttemptOutcome
    decline: DeclineInfo | None = None
    gateway_request_id: str | None = None
    gateway_response_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Receive a synthetic gateway event",
    response_model=IngestPaymentAttemptResult,
)
async def mock_gateway_webhook(
    payload: MockGatewayPayload,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> IngestPaymentAttemptResult:
    """Ingest a synthetic payment attempt and persist it through the saga."""
    cmd = IngestPaymentAttemptCommand(
        command_id=new_command_id(),
        tenant_id=tenant_id,
        external_id=payload.external_id,
        transaction_seed=TransactionSeed(
            amount_cents=payload.amount_cents,
            currency=payload.currency,
            card=payload.card,
            gateway_provider=payload.gateway_provider,
            gateway_account_ref=payload.gateway_account_ref,
            customer_ref=payload.customer_ref,
        ),
        outcome=payload.outcome,
        decline=payload.decline,
        gateway_request_id=payload.gateway_request_id,
        gateway_response_id=payload.gateway_response_id,
        latency_ms=payload.latency_ms,
    )
    handler = IngestPaymentAttemptHandler(session=session)
    return await handler.handle(cmd)
