"""Domain events for the recovery context.

Every state transition is an event; the aggregate has zero implicit state.
This is the saga's audit trail, and it's what the Trust View timeline reads.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import ConfigDict, Field

from reflow.core.events.event import DomainEvent
from reflow.core.events.registry import register_event
from reflow.core.types import (
    DiagnosisId,
    ExecutionAttemptId,
    PolicyDecisionId,
    RecoveryId,
    RiskAssessmentId,
    StrategyId,
    TransactionId,
)
from reflow.domain.policy import PolicyOutcome
from reflow.domain.recovery.value_objects import ExecutionOutcome, RecoveryStrategy


class _RecEvent(DomainEvent):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stream_type: ClassVar[str] = "recovery"

    recovery_id: RecoveryId

    def stream_id(self) -> str:
        return f"recovery-{self.recovery_id}"


@register_event
class RecoveryCreated(_RecEvent):
    event_type: ClassVar[str] = "RecoveryCreated"

    transaction_id: TransactionId
    recovery_key: str = Field(
        description="Deterministic idempotency key for this recovery."
    )


@register_event
class RecoveryDiagnosed(_RecEvent):
    event_type: ClassVar[str] = "RecoveryDiagnosed"

    diagnosis_id: DiagnosisId
    root_cause_category: str
    is_recoverable: bool
    confidence: float = Field(ge=0, le=1)


@register_event
class RecoveryStrategyProposed(_RecEvent):
    event_type: ClassVar[str] = "RecoveryStrategyProposed"

    strategy_id: StrategyId
    strategy: RecoveryStrategy


@register_event
class RecoveryRiskAssessed(_RecEvent):
    event_type: ClassVar[str] = "RecoveryRiskAssessed"

    risk_assessment_id: RiskAssessmentId
    overall_risk_level: str
    duplicate_charge_probability: float = Field(ge=0, le=1)


@register_event
class RecoveryPolicyEvaluated(_RecEvent):
    event_type: ClassVar[str] = "RecoveryPolicyEvaluated"

    policy_decision_id: PolicyDecisionId
    outcome: PolicyOutcome
    matched_rule_id: str | None = None
    reason: str


@register_event
class RecoveryApprovalRequested(_RecEvent):
    event_type: ClassVar[str] = "RecoveryApprovalRequested"

    reason: str


@register_event
class RecoveryApproved(_RecEvent):
    event_type: ClassVar[str] = "RecoveryApproved"

    approver_id: str | None = None
    approval_note: str | None = None


@register_event
class RecoveryRejected(_RecEvent):
    event_type: ClassVar[str] = "RecoveryRejected"

    rejector_id: str | None = None
    rejection_reason: str


@register_event
class RecoveryExecutionStarted(_RecEvent):
    event_type: ClassVar[str] = "RecoveryExecutionStarted"

    execution_attempt_id: ExecutionAttemptId
    gateway_id: str
    idempotency_key: str


@register_event
class RecoveryExecutionCompleted(_RecEvent):
    event_type: ClassVar[str] = "RecoveryExecutionCompleted"

    execution_attempt_id: ExecutionAttemptId
    outcome: ExecutionOutcome
    decline_code: str | None = None
    latency_ms: int | None = None


@register_event
class RecoverySucceeded(_RecEvent):
    event_type: ClassVar[str] = "RecoverySucceeded"

    recovered_amount_cents: int = Field(gt=0)


@register_event
class RecoveryFailed(_RecEvent):
    event_type: ClassVar[str] = "RecoveryFailed"

    reason: str


@register_event
class RecoveryAbandoned(_RecEvent):
    event_type: ClassVar[str] = "RecoveryAbandoned"

    reason: str
