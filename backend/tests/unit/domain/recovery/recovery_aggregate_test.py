"""Recovery aggregate — the saga state machine.

Every transition is asserted, every illegal transition is rejected. The
'happy path' test walks the full saga from CREATED to RECOVERED.
"""

from __future__ import annotations

import pytest

from reflow.core.exceptions import InvariantViolationError
from reflow.core.types import (
    DiagnosisId,
    ExecutionAttemptId,
    PolicyDecisionId,
    RiskAssessmentId,
    StrategyId,
    new_id,
    new_tenant_id,
    new_transaction_id,
)
from reflow.domain.policy import PolicyOutcome, RecoveryStrategyKind
from reflow.domain.recovery import (
    ExecutionOutcome,
    Recovery,
    RecoveryState,
    RecoveryStrategy,
)

pytestmark = pytest.mark.unit


def _start() -> Recovery:
    return Recovery.start(
        recovery_id=Recovery.new_id(),
        tenant_id=new_tenant_id(),
        transaction_id=new_transaction_id(),
        attempt_number=1,
    )


def _diagnose(rec: Recovery, confidence: float = 0.9) -> None:
    rec.diagnose(
        diagnosis_id=DiagnosisId(new_id()),
        root_cause_category="issuer_decline",
        is_recoverable=True,
        confidence=confidence,
    )


def _propose_strategy(rec: Recovery) -> None:
    rec.propose_strategy(
        strategy_id=StrategyId(new_id()),
        strategy=RecoveryStrategy(
            kind=RecoveryStrategyKind.DELAYED_RETRY,
            parameters={"delay_seconds": 60},
            expected_recovery_probability=0.65,
        ),
    )


def _assess_risk(rec: Recovery, dup_p: float = 0.01) -> None:
    rec.assess_risk(
        risk_assessment_id=RiskAssessmentId(new_id()),
        overall_risk_level="low",
        duplicate_charge_probability=dup_p,
    )


def _evaluate(rec: Recovery, outcome: PolicyOutcome, reason: str = "ok") -> None:
    rec.evaluate_policy(
        policy_decision_id=PolicyDecisionId(new_id()),
        outcome=outcome,
        matched_rule_id=None if outcome == PolicyOutcome.ALLOW else "test.rule",
        reason=reason,
    )


# -----------------------------------------------------------------------------
# Construction
# -----------------------------------------------------------------------------


class TestStart:
    def test_start_emits_recovery_created(self) -> None:
        rec = _start()
        pending = rec.pull_pending_events()
        assert len(pending) == 1
        assert type(pending[0]).__name__ == "RecoveryCreated"
        assert rec.state == RecoveryState.CREATED

    def test_recovery_key_is_deterministic_per_attempt(self) -> None:
        tid = new_transaction_id()
        ten = new_tenant_id()
        a = Recovery.start(
            recovery_id=Recovery.new_id(),
            tenant_id=ten,
            transaction_id=tid,
            attempt_number=2,
        )
        b = Recovery.start(
            recovery_id=Recovery.new_id(),
            tenant_id=ten,
            transaction_id=tid,
            attempt_number=2,
        )
        assert a.recovery_key == b.recovery_key

    def test_invalid_attempt_number_rejected(self) -> None:
        with pytest.raises(InvariantViolationError, match="attempt_number"):
            Recovery.start(
                recovery_id=Recovery.new_id(),
                tenant_id=new_tenant_id(),
                transaction_id=new_transaction_id(),
                attempt_number=0,
            )


# -----------------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------------


class TestHappyPath:
    def test_full_saga_to_recovered(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.ALLOW)

        rec.start_execution(
            execution_attempt_id=ExecutionAttemptId(new_id()),
            gateway_id="stripe",
            idempotency_key=rec.recovery_key,
        )
        assert rec.state == RecoveryState.EXECUTING

        rec.complete_execution(outcome=ExecutionOutcome.SUCCESS, latency_ms=420)
        assert rec.state == RecoveryState.EXECUTED

        rec.succeed(recovered_amount_cents=5_000)
        assert rec.state == RecoveryState.RECOVERED
        assert rec.recovered_amount_cents == 5_000

    def test_full_saga_through_approval(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.REQUIRE_APPROVAL, reason="high value")

        assert rec.state == RecoveryState.AWAITING_APPROVAL

        rec.approve(approver_id="user-1")
        assert rec.state == RecoveryState.APPROVED

        rec.start_execution(
            execution_attempt_id=ExecutionAttemptId(new_id()),
            gateway_id="stripe",
            idempotency_key=rec.recovery_key,
        )
        rec.complete_execution(outcome=ExecutionOutcome.SUCCESS)
        rec.succeed(recovered_amount_cents=200_000)
        assert rec.state == RecoveryState.RECOVERED


# -----------------------------------------------------------------------------
# Failure paths
# -----------------------------------------------------------------------------


class TestFailure:
    def test_policy_deny_transitions_to_failed(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.DENY, reason="duplicate risk")
        assert rec.state == RecoveryState.FAILED
        assert rec.failure_reason is not None
        assert "duplicate risk" in rec.failure_reason

    def test_rejected_approval_fails(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.REQUIRE_APPROVAL)
        rec.reject(rejector_id="user-2", rejection_reason="risk too high")
        assert rec.state == RecoveryState.FAILED
        assert rec.failure_reason == "risk too high"

    def test_failed_execution_transitions_to_failed(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.ALLOW)
        rec.start_execution(
            execution_attempt_id=ExecutionAttemptId(new_id()),
            gateway_id="stripe",
            idempotency_key=rec.recovery_key,
        )
        rec.complete_execution(outcome=ExecutionOutcome.FAILURE, decline_code="hard_decline")
        assert rec.state == RecoveryState.FAILED


# -----------------------------------------------------------------------------
# Illegal transitions
# -----------------------------------------------------------------------------


class TestIllegalTransitions:
    def test_cannot_diagnose_twice(self) -> None:
        rec = _start()
        _diagnose(rec)
        with pytest.raises(InvariantViolationError):
            _diagnose(rec)

    def test_cannot_skip_diagnosis(self) -> None:
        rec = _start()
        with pytest.raises(InvariantViolationError):
            _propose_strategy(rec)

    def test_cannot_execute_without_policy_evaluation(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        with pytest.raises(InvariantViolationError):
            rec.start_execution(
                execution_attempt_id=ExecutionAttemptId(new_id()),
                gateway_id="stripe",
                idempotency_key=rec.recovery_key,
            )

    def test_cannot_succeed_without_execution(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.ALLOW)
        with pytest.raises(InvariantViolationError):
            rec.succeed(recovered_amount_cents=5_000)

    def test_cannot_abandon_terminal(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.DENY)
        with pytest.raises(InvariantViolationError):
            rec.abandon(reason="too late")

    def test_cannot_complete_execution_without_starting(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.ALLOW)
        with pytest.raises(InvariantViolationError):
            rec.complete_execution(outcome=ExecutionOutcome.SUCCESS)

    def test_succeed_with_zero_amount_rejected(self) -> None:
        rec = _start()
        _diagnose(rec)
        _propose_strategy(rec)
        _assess_risk(rec)
        _evaluate(rec, PolicyOutcome.ALLOW)
        rec.start_execution(
            execution_attempt_id=ExecutionAttemptId(new_id()),
            gateway_id="stripe",
            idempotency_key=rec.recovery_key,
        )
        rec.complete_execution(outcome=ExecutionOutcome.SUCCESS)
        with pytest.raises(InvariantViolationError, match="positive"):
            rec.succeed(recovered_amount_cents=0)

    def test_diagnose_with_out_of_range_confidence_rejected(self) -> None:
        rec = _start()
        with pytest.raises(InvariantViolationError, match="confidence"):
            _diagnose(rec, confidence=1.5)


# -----------------------------------------------------------------------------
# Replay
# -----------------------------------------------------------------------------


class TestReplay:
    def test_replay_reproduces_state(self) -> None:
        origin = _start()
        _diagnose(origin)
        _propose_strategy(origin)
        _assess_risk(origin)
        _evaluate(origin, PolicyOutcome.ALLOW)
        events = origin.pull_pending_events()

        replayed = Recovery.replay(events)
        assert replayed.state == origin.state
        assert replayed.diagnosis_id == origin.diagnosis_id
        assert replayed.strategy_id == origin.strategy_id
        assert replayed.policy_decision_id == origin.policy_decision_id
        assert replayed.version == len(events)
        assert replayed.pull_pending_events() == []

    def test_replay_empty_rejected(self) -> None:
        with pytest.raises(InvariantViolationError):
            Recovery.replay([])

    def test_replay_first_event_must_be_recovery_created(self) -> None:
        origin = _start()
        _diagnose(origin)
        events = origin.pull_pending_events()
        with pytest.raises(InvariantViolationError):
            Recovery.replay(events[1:])
