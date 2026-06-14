"""Concrete TransactionRepository.

Event-sourced: every state change is persisted as events first, then projected
to the `txn.transactions` / `txn.attempts` read model in the same transaction.
Single-aggregate reads (`load`) thus never lag.

This repository implements the `TransactionRepository` Protocol from the
domain layer. It depends on the EventStoreRepository for event persistence
and writes its own rows to the read-model tables.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.types import TransactionId
from reflow.domain.transactions import (
    AttemptOutcome,
    AttemptRecorded,
    PaymentAbandoned,
    PaymentFailed,
    PaymentRecovered,
    Transaction,
    TransactionCreated,
    TransactionStatus,
)
from reflow.infrastructure.persistence.models import AttemptModel, TransactionModel
from reflow.infrastructure.persistence.repositories.event_store_repository import (
    EventStoreRepository,
)


class SqlTransactionRepository:
    """Event-sourced TransactionRepository.

    `load` reconstructs the aggregate by replaying its stream.
    `save` appends pending events + updates the read model atomically.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventStoreRepository(session)

    # ---- Read --------------------------------------------------------------
    async def load(self, transaction_id: TransactionId) -> Transaction | None:
        # Read tenant_id from the read model so we can materialize the stream.
        existing = await self._session.execute(
            select(TransactionModel.tenant_id).where(TransactionModel.id == transaction_id)
        )
        tenant_id_row = existing.scalar_one_or_none()
        if tenant_id_row is None:
            # Stream may exist without a read-model row in failure modes —
            # but normal path always writes both.  Treat absent read model as not found.
            return None

        events = await self._events.materialize_stream(
            stream_id=f"transaction-{transaction_id}",
            tenant_id=tenant_id_row,  # type: ignore[arg-type]
        )
        if not events:
            return None
        return Transaction.replay(events)

    # ---- Write -------------------------------------------------------------
    async def save(self, transaction: Transaction) -> None:
        pending = transaction.pull_pending_events()
        if not pending:
            return

        await self._events.append_events(
            stream_id=f"transaction-{transaction.id}",
            expected_version=transaction.version,
            events=pending,
        )

        for event in pending:
            await self._project(event)

        transaction.version += len(pending)

    # ---- Projections -------------------------------------------------------
    async def _project(self, event: object) -> None:
        match event:
            case TransactionCreated() as ev:
                stmt = pg_insert(TransactionModel).values(
                    id=ev.transaction_id,
                    tenant_id=ev.tenant_id,
                    external_id=ev.external_id,
                    customer_ref=ev.customer_ref,
                    amount_cents=ev.amount_cents,
                    currency=ev.currency,
                    card_bin=ev.card.bin,
                    card_last4=ev.card.last4,
                    card_brand=ev.card.brand,
                    card_funding=ev.card.funding.value,
                    card_country=ev.card.country,
                    gateway_id=ev.gateway_provider,
                    status=TransactionStatus.PENDING.value,
                    created_at=ev.occurred_at,
                    updated_at=ev.occurred_at,
                )
                # ON CONFLICT DO NOTHING: re-projection of the same event is idempotent.
                stmt = stmt.on_conflict_do_nothing(index_elements=[TransactionModel.id])
                await self._session.execute(stmt)

            case AttemptRecorded() as ev:
                stmt = pg_insert(AttemptModel).values(
                    id=ev.attempt_id,
                    tenant_id=ev.tenant_id,
                    transaction_id=ev.transaction_id,
                    attempt_number=ev.attempt_number,
                    gateway_id=ev.gateway_provider,
                    gateway_request_id=ev.gateway_request_id,
                    gateway_response_id=ev.gateway_response_id,
                    outcome=ev.outcome.value,
                    decline_code=ev.decline.code_raw if ev.decline else None,
                    decline_code_normalized=ev.decline.code_normalized if ev.decline else None,
                    decline_category=ev.decline.category.value if ev.decline else None,
                    decline_message=ev.decline.message if ev.decline else None,
                    latency_ms=ev.latency_ms,
                    attempted_at=ev.occurred_at,
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=[AttemptModel.id])
                await self._session.execute(stmt)

                if ev.outcome == AttemptOutcome.SUCCESS:
                    await self._update_txn_status(
                        ev.transaction_id,
                        status=TransactionStatus.SUCCEEDED.value,
                        final_resolved_at=ev.occurred_at,
                    )

            case PaymentFailed() as ev:
                await self._update_txn_status(
                    ev.transaction_id,
                    status=TransactionStatus.FAILED.value,
                    initial_failed_at=ev.occurred_at,
                )

            case PaymentRecovered() as ev:
                await self._update_txn_status(
                    ev.transaction_id,
                    status=TransactionStatus.RECOVERED.value,
                    final_resolved_at=ev.occurred_at,
                )

            case PaymentAbandoned() as ev:
                await self._update_txn_status(
                    ev.transaction_id,
                    status=TransactionStatus.ABANDONED.value,
                    final_resolved_at=ev.occurred_at,
                )

    async def _update_txn_status(
        self,
        transaction_id: TransactionId,
        *,
        status: str,
        initial_failed_at: datetime | None = None,
        final_resolved_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {
            "status": status,
            "updated_at": datetime.now(UTC),
        }
        if initial_failed_at is not None:
            values["initial_failed_at"] = initial_failed_at
        if final_resolved_at is not None:
            values["final_resolved_at"] = final_resolved_at

        await self._session.execute(
            update(TransactionModel)
            .where(TransactionModel.id == transaction_id)
            .values(**values)
        )
