"""Transaction aggregate.

A Transaction is the unit of business interaction (one charge attempt the
merchant cares about).  The aggregate carries:
    * a current state (pending, failed, recovering, recovered, ...)
    * a list of attempts (the audit trail of charge tries)
    * pending events to emit (so command handlers can flush them via the
      event store repository)

The aggregate is rebuilt by replaying events.  Commands return either
nothing (success) or raise an `InvariantViolationError`.

This is pure domain code — no SQLAlchemy, no Redis, no HTTP. It can be
unit-tested without spinning up infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from reflow.core.events.event import DomainEvent, EventMetadata
from reflow.core.exceptions import InvariantViolationError
from reflow.core.types import (
    AttemptId,
    TenantId,
    TransactionId,
    new_id,
)
from reflow.domain.transactions.events import (
    AttemptRecorded,
    PaymentAbandoned,
    PaymentFailed,
    PaymentRecovered,
    TransactionCreated,
)
from reflow.domain.transactions.value_objects import (
    AttemptOutcome,
    CardMetadata,
    CurrencyCode,
    DeclineInfo,
    TransactionStatus,
)


@dataclass(slots=True)
class AttemptView:
    """In-memory view of a single attempt (projected from events)."""

    id: AttemptId
    attempt_number: int
    outcome: AttemptOutcome
    decline: DeclineInfo | None
    occurred_at: datetime


@dataclass(slots=True)
class Transaction:
    """The Transaction aggregate.

    Invariants enforced here (and again at DB layer):
        * Cannot create a transaction twice.
        * Attempts numbered monotonically from 1.
        * Cannot record attempts after recovered/abandoned.
        * Cannot recover a transaction that wasn't failed.
    """

    id: TransactionId
    tenant_id: TenantId
    external_id: str
    amount_cents: int
    currency: CurrencyCode
    card: CardMetadata
    gateway_provider: str
    gateway_account_ref: str | None
    customer_ref: str | None

    status: TransactionStatus = TransactionStatus.PENDING
    attempts: list[AttemptView] = field(default_factory=list)
    version: int = 0  # last persisted version; 0 = brand new

    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)

    # -------------------------------------------------------------------------
    # Factory / commands
    # -------------------------------------------------------------------------
    @classmethod
    def create(  # noqa: PLR0913 — value-object inputs, all required
        cls,
        *,
        transaction_id: TransactionId,
        tenant_id: TenantId,
        external_id: str,
        amount_cents: int,
        currency: CurrencyCode,
        card: CardMetadata,
        gateway_provider: str,
        gateway_account_ref: str | None = None,
        customer_ref: str | None = None,
        metadata: EventMetadata | None = None,
    ) -> Transaction:
        if amount_cents <= 0:
            raise InvariantViolationError("Transaction amount must be positive")

        txn = cls(
            id=transaction_id,
            tenant_id=tenant_id,
            external_id=external_id,
            amount_cents=amount_cents,
            currency=currency,
            card=card,
            gateway_provider=gateway_provider,
            gateway_account_ref=gateway_account_ref,
            customer_ref=customer_ref,
        )
        txn._apply(
            TransactionCreated(
                tenant_id=tenant_id,
                transaction_id=transaction_id,
                external_id=external_id,
                customer_ref=customer_ref,
                amount_cents=amount_cents,
                currency=currency,
                card=card,
                gateway_provider=gateway_provider,
                gateway_account_ref=gateway_account_ref,
                metadata=metadata or EventMetadata(),
            ),
            record_pending=True,
        )
        return txn

    def record_attempt(
        self,
        *,
        outcome: AttemptOutcome,
        decline: DeclineInfo | None = None,
        gateway_request_id: str | None = None,
        gateway_response_id: str | None = None,
        latency_ms: int | None = None,
        metadata: EventMetadata | None = None,
    ) -> AttemptId:
        if self.is_terminal:
            raise InvariantViolationError(
                f"Cannot record attempt on terminal transaction (status={self.status})"
            )
        if outcome in {AttemptOutcome.SOFT_DECLINE, AttemptOutcome.HARD_DECLINE} and decline is None:
            raise InvariantViolationError("Decline outcomes require a DeclineInfo")

        attempt_id = AttemptId(new_id())
        attempt_number = len(self.attempts) + 1

        self._apply(
            AttemptRecorded(
                tenant_id=self.tenant_id,
                transaction_id=self.id,
                attempt_id=attempt_id,
                attempt_number=attempt_number,
                gateway_provider=self.gateway_provider,
                gateway_request_id=gateway_request_id,
                gateway_response_id=gateway_response_id,
                outcome=outcome,
                decline=decline,
                latency_ms=latency_ms,
                metadata=metadata or EventMetadata(),
            ),
            record_pending=True,
        )

        if outcome in {AttemptOutcome.SOFT_DECLINE, AttemptOutcome.HARD_DECLINE} and decline is not None:
            assert decline is not None  # noqa: S101 — narrowed above
            self._apply(
                PaymentFailed(
                    tenant_id=self.tenant_id,
                    transaction_id=self.id,
                    triggering_attempt_id=attempt_id,
                    decline=decline,
                    metadata=metadata or EventMetadata(),
                ),
                record_pending=True,
            )

        return attempt_id

    def mark_recovered(
        self,
        *,
        recovery_attempt_id: AttemptId,
        recovered_amount_cents: int,
        metadata: EventMetadata | None = None,
    ) -> None:
        if self.status not in {TransactionStatus.FAILED, TransactionStatus.RECOVERING}:
            raise InvariantViolationError(
                f"Cannot mark recovered from status {self.status!r}"
            )
        if recovered_amount_cents <= 0:
            raise InvariantViolationError("Recovered amount must be positive")
        self._apply(
            PaymentRecovered(
                tenant_id=self.tenant_id,
                transaction_id=self.id,
                recovery_attempt_id=recovery_attempt_id,
                recovered_amount_cents=recovered_amount_cents,
                metadata=metadata or EventMetadata(),
            ),
            record_pending=True,
        )

    def abandon(self, *, reason: str, metadata: EventMetadata | None = None) -> None:
        if self.is_terminal:
            raise InvariantViolationError(
                f"Cannot abandon terminal transaction (status={self.status})"
            )
        self._apply(
            PaymentAbandoned(
                tenant_id=self.tenant_id,
                transaction_id=self.id,
                reason=reason,
                metadata=metadata or EventMetadata(),
            ),
            record_pending=True,
        )

    # -------------------------------------------------------------------------
    # Rehydration
    # -------------------------------------------------------------------------
    @classmethod
    def replay(cls, events: list[DomainEvent]) -> Transaction:
        if not events:
            raise InvariantViolationError("Cannot replay empty event list")
        first = events[0]
        if not isinstance(first, TransactionCreated):
            raise InvariantViolationError(
                f"First event must be TransactionCreated, got {type(first).__name__}"
            )
        txn = cls(
            id=first.transaction_id,
            tenant_id=first.tenant_id,
            external_id=first.external_id,
            amount_cents=first.amount_cents,
            currency=first.currency,
            card=first.card,
            gateway_provider=first.gateway_provider,
            gateway_account_ref=first.gateway_account_ref,
            customer_ref=first.customer_ref,
        )
        for ev in events:
            txn._apply(ev, record_pending=False)
            txn.version += 1
        return txn

    # -------------------------------------------------------------------------
    # Pending events for the repository
    # -------------------------------------------------------------------------
    def pull_pending_events(self) -> list[DomainEvent]:
        out = list(self._pending_events)
        self._pending_events.clear()
        return out

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------
    @property
    def is_terminal(self) -> bool:
        return self.status in {TransactionStatus.RECOVERED, TransactionStatus.ABANDONED}

    def _apply(self, event: DomainEvent, *, record_pending: bool) -> None:
        match event:
            case TransactionCreated():
                # Initial state already set by `create`; no transition here.
                pass
            case AttemptRecorded():
                self.attempts.append(
                    AttemptView(
                        id=event.attempt_id,
                        attempt_number=event.attempt_number,
                        outcome=event.outcome,
                        decline=event.decline,
                        occurred_at=event.occurred_at,
                    )
                )
                if event.outcome == AttemptOutcome.SUCCESS:
                    self.status = TransactionStatus.SUCCEEDED
            case PaymentFailed():
                self.status = TransactionStatus.FAILED
            case PaymentRecovered():
                self.status = TransactionStatus.RECOVERED
            case PaymentAbandoned():
                self.status = TransactionStatus.ABANDONED
            case _:
                raise InvariantViolationError(
                    f"Unknown event type in Transaction stream: {type(event).__name__}"
                )

        if record_pending:
            self._pending_events.append(event)

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id}, status={self.status.value}, "
            f"attempts={len(self.attempts)}, version={self.version})"
        )

    # For tests that need a deterministic clock; kept here so the aggregate
    # owns its temporal vocabulary.
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
