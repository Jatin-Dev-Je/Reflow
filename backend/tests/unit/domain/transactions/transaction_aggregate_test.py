"""Transaction aggregate — pure unit tests.

Exercises invariants, state transitions, and event emission. No I/O.
"""

from __future__ import annotations

import pytest

from reflow.core.exceptions import InvariantViolationError
from reflow.core.types import (
    TenantId,
    TransactionId,
    new_id,
    new_tenant_id,
    new_transaction_id,
)
from reflow.domain.transactions import (
    AttemptOutcome,
    AttemptRecorded,
    CardFunding,
    CardMetadata,
    DeclineCategory,
    DeclineInfo,
    PaymentAbandoned,
    PaymentFailed,
    PaymentRecovered,
    Transaction,
    TransactionCreated,
    TransactionStatus,
)

pytestmark = pytest.mark.unit


def _card() -> CardMetadata:
    return CardMetadata(
        bin="424242", last4="4242", brand="visa", funding=CardFunding.CREDIT, country="US"
    )


def _decline(category: DeclineCategory = DeclineCategory.FUNDS) -> DeclineInfo:
    return DeclineInfo(
        code_raw="insufficient_funds",
        code_normalized="FUNDS_INSUFFICIENT",
        category=category,
        message="Insufficient funds",
    )


def _new_txn(
    *,
    tenant: TenantId | None = None,
    txn_id: TransactionId | None = None,
    amount_cents: int = 5000,
) -> Transaction:
    return Transaction.create(
        transaction_id=txn_id or new_transaction_id(),
        tenant_id=tenant or new_tenant_id(),
        external_id="ext_" + str(new_id())[:8],
        amount_cents=amount_cents,
        currency="USD",
        card=_card(),
        gateway_provider="stripe",
        customer_ref="cust_42",
    )


class TestCreation:
    def test_create_emits_transaction_created_event(self) -> None:
        txn = _new_txn()
        pending = txn.pull_pending_events()
        assert len(pending) == 1
        assert isinstance(pending[0], TransactionCreated)
        assert txn.status == TransactionStatus.PENDING

    def test_create_with_zero_amount_rejected(self) -> None:
        with pytest.raises(InvariantViolationError, match="positive"):
            Transaction.create(
                transaction_id=new_transaction_id(),
                tenant_id=new_tenant_id(),
                external_id="ext",
                amount_cents=0,
                currency="USD",
                card=_card(),
                gateway_provider="stripe",
            )

    def test_create_with_negative_amount_rejected(self) -> None:
        with pytest.raises(InvariantViolationError, match="positive"):
            Transaction.create(
                transaction_id=new_transaction_id(),
                tenant_id=new_tenant_id(),
                external_id="ext",
                amount_cents=-100,
                currency="USD",
                card=_card(),
                gateway_provider="stripe",
            )


class TestAttemptRecording:
    def test_first_attempt_is_numbered_one(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()  # drain creation event

        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        assert txn.attempts[0].attempt_number == 1

    def test_decline_requires_decline_info(self) -> None:
        txn = _new_txn()
        with pytest.raises(InvariantViolationError, match="DeclineInfo"):
            txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=None)

    def test_success_attempt_transitions_to_succeeded(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SUCCESS)
        assert txn.status == TransactionStatus.SUCCEEDED

    def test_soft_decline_emits_both_attempt_recorded_and_payment_failed(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        pending = txn.pull_pending_events()
        kinds = [type(e).__name__ for e in pending]
        assert kinds == ["AttemptRecorded", "PaymentFailed"]
        assert txn.status == TransactionStatus.FAILED

    def test_hard_decline_also_emits_payment_failed(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.HARD_DECLINE, decline=_decline())
        assert txn.status == TransactionStatus.FAILED

    def test_attempt_after_terminal_state_rejected(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        attempt_id = txn.attempts[0].id
        txn.mark_recovered(recovery_attempt_id=attempt_id, recovered_amount_cents=5000)
        with pytest.raises(InvariantViolationError, match="terminal"):
            txn.record_attempt(outcome=AttemptOutcome.SUCCESS)


class TestRecovery:
    def test_recovery_from_failed_state(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        attempt_id = txn.attempts[0].id
        _ = txn.pull_pending_events()

        txn.mark_recovered(recovery_attempt_id=attempt_id, recovered_amount_cents=5000)
        pending = txn.pull_pending_events()
        assert any(isinstance(e, PaymentRecovered) for e in pending)
        assert txn.status == TransactionStatus.RECOVERED

    def test_cannot_recover_pending_transaction(self) -> None:
        txn = _new_txn()
        with pytest.raises(InvariantViolationError, match="Cannot mark recovered"):
            txn.mark_recovered(recovery_attempt_id=new_id(), recovered_amount_cents=5000)  # type: ignore[arg-type]

    def test_cannot_recover_with_zero_amount(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        attempt_id = txn.attempts[0].id
        with pytest.raises(InvariantViolationError, match="positive"):
            txn.mark_recovered(recovery_attempt_id=attempt_id, recovered_amount_cents=0)


class TestAbandon:
    def test_abandon_from_failed(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        _ = txn.pull_pending_events()

        txn.abandon(reason="retry budget exhausted")
        assert any(isinstance(e, PaymentAbandoned) for e in txn.pull_pending_events())
        assert txn.status == TransactionStatus.ABANDONED

    def test_cannot_abandon_recovered_transaction(self) -> None:
        txn = _new_txn()
        _ = txn.pull_pending_events()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        attempt_id = txn.attempts[0].id
        txn.mark_recovered(recovery_attempt_id=attempt_id, recovered_amount_cents=5000)
        with pytest.raises(InvariantViolationError, match="terminal"):
            txn.abandon(reason="should fail")


class TestReplay:
    def test_replay_reproduces_state(self) -> None:
        origin = _new_txn()
        origin.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        events = origin.pull_pending_events()

        replayed = Transaction.replay(events)
        assert replayed.id == origin.id
        assert replayed.status == origin.status
        assert len(replayed.attempts) == len(origin.attempts)
        assert replayed.version == len(events)
        # Replay must NOT carry over pending events.
        assert replayed.pull_pending_events() == []

    def test_replay_with_empty_list_rejected(self) -> None:
        with pytest.raises(InvariantViolationError, match="empty"):
            Transaction.replay([])

    def test_replay_first_event_must_be_transaction_created(self) -> None:
        txn = _new_txn()
        txn.record_attempt(outcome=AttemptOutcome.SOFT_DECLINE, decline=_decline())
        events = txn.pull_pending_events()
        # Drop the first event — sequence is invalid.
        with pytest.raises(InvariantViolationError, match="TransactionCreated"):
            Transaction.replay(events[1:])
