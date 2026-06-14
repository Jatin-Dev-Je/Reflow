"""Ingest a payment attempt event.

Use case:
    * Webhook (or simulator) reports a charge attempt.
    * If we've never seen this `(tenant_id, external_id)`, create the
      transaction; otherwise load it and append a new attempt.
    * Save via the repository: events to the store + projection to the
      read model, all in one DB transaction.

This handler is the canonical example of how every command in Reflow looks:
    1. Resolve aggregate (load or create)
    2. Invoke domain command method
    3. Save through repository
    4. Return a result DTO
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.events.event import EventMetadata
from reflow.core.observability.logging import get_logger
from reflow.core.types import (
    TransactionId,
    new_command_id,
    new_transaction_id,
)
from reflow.domain.transactions import Transaction
from reflow.infrastructure.persistence.models import TransactionModel
from reflow.infrastructure.persistence.repositories import SqlTransactionRepository

from reflow.application.transactions.dto import (
    IngestPaymentAttemptCommand,
    IngestPaymentAttemptResult,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IngestPaymentAttemptHandler:
    """Application service for IngestPaymentAttempt."""

    session: AsyncSession

    async def handle(self, cmd: IngestPaymentAttemptCommand) -> IngestPaymentAttemptResult:
        repo = SqlTransactionRepository(self.session)
        command_id = cmd.command_id or new_command_id()

        # Look up the transaction by (tenant, external_id) — the merchant's idempotency key.
        existing_id = await self._lookup_transaction_id(cmd.tenant_id, cmd.external_id)

        if existing_id is None:
            txn = self._create_new(cmd, command_id)
            created_new = True
        else:
            loaded = await repo.load(existing_id)
            if loaded is None:
                # Read model points to a stream we can't materialize — escalate.
                # This is a real failure, not a "not found" — surface loudly.
                msg = f"Read model points at transaction {existing_id} but stream is unreadable"
                _logger.error("transactions.load_inconsistent", transaction_id=str(existing_id))
                raise RuntimeError(msg)
            txn = loaded
            created_new = False

        # Apply the new attempt to the aggregate.
        attempt_id = txn.record_attempt(
            outcome=cmd.outcome,
            decline=cmd.decline,
            gateway_request_id=cmd.gateway_request_id,
            gateway_response_id=cmd.gateway_response_id,
            latency_ms=cmd.latency_ms,
            metadata=EventMetadata(command_id=command_id, source="application:ingest"),
        )

        await repo.save(txn)

        _logger.info(
            "transactions.attempt_recorded",
            transaction_id=str(txn.id),
            attempt_id=str(attempt_id),
            attempt_number=len(txn.attempts),
            outcome=cmd.outcome.value,
            created_new_transaction=created_new,
        )

        return IngestPaymentAttemptResult(
            transaction_id=txn.id,
            attempt_id=str(attempt_id),
            attempt_number=len(txn.attempts),
            status=txn.status.value,
            created_new_transaction=created_new,
        )

    async def _lookup_transaction_id(
        self, tenant_id: object, external_id: str
    ) -> TransactionId | None:
        stmt = select(TransactionModel.id).where(
            (TransactionModel.tenant_id == tenant_id)
            & (TransactionModel.external_id == external_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _create_new(cmd: IngestPaymentAttemptCommand, command_id: object) -> Transaction:
        seed = cmd.transaction_seed
        return Transaction.create(
            transaction_id=new_transaction_id(),
            tenant_id=cmd.tenant_id,
            external_id=cmd.external_id,
            amount_cents=seed.amount_cents,
            currency=seed.currency,
            card=seed.card,
            gateway_provider=seed.gateway_provider,
            gateway_account_ref=seed.gateway_account_ref,
            customer_ref=seed.customer_ref,
            metadata=EventMetadata(
                command_id=command_id,  # type: ignore[arg-type]
                source="application:ingest",
            ),
        )
