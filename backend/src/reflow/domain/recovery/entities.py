"""Recovery aggregate — the saga state machine.

State transitions explicitly enumerated in `_VALID_TRANSITIONS` rather than
implied by event order. This makes auditing the legal paths easy and gives
us a single place to enforce 'no skipping the policy check' style guarantees.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from reflow.core.events.event import DomainEvent, EventMetadata
from reflow.core.exceptions import InvariantViolationError
from reflow.core.types import (
    DiagnosisId,
    ExecutionAttemptId,
    PolicyDecisionId,
    RecoveryId,
    RiskAssessmentId,
    StrategyId,
    TenantId,
    TransactionId,
    new_id,
)
from reflow.domain.policy import PolicyOutcome
from reflow.domain.recovery.events import (
    RecoveryAbandoned,
    RecoveryApprovalRequested,
    RecoveryApproved,
    RecoveryCreated,
    RecoveryDiagnosed,
    RecoveryExecutionCompleted,
    RecoveryExecutionStarted,
    RecoveryFailed,
    RecoveryPolicyEvaluated,
    RecoveryRejected,
    RecoveryRiskAssessed,
    RecoveryStrategyProposed,
    RecoverySucceeded,
)
from reflow.domain.recovery.value_objects import (
    TERMINAL_STATES,
    ExecutionOutcome,
    RecoveryState,
    RecoveryStrategy,
)


# Legal transitions. Each entry maps from_state -> set of allowed to_states.
_VALID_TRANSITIONS: dict[RecoveryState, frozenset[RecoveryState]] = {
    RecoveryState.CREATED: frozenset({RecoveryState.DIAGNOSED, RecoveryState.FAILED}),
    RecoveryState.DIAGNOSED: frozenset(
        {RecoveryState.STRATEGY_PROPOSED, RecoveryState.ABANDONED}
    ),
    RecoveryState.STRATEGY_PROPOSED: frozenset({RecoveryState.RISK_ASSESSED}),
    RecoveryState.RISK_ASSESSED: frozenset({RecoveryState.POLICY_EVALUATED}),
    RecoveryState.POLICY_EVALUATED: frozenset(
        {RecoveryState.EXECUTING, RecoveryState.AWAITING_APPROVAL, RecoveryState.FAILED}
    ),
    RecoveryState.AWAITING_APPROVAL: frozenset(
        {RecoveryState.APPROVED, RecoveryState.FAILED}
    ),
    RecoveryState.APPROVED: frozenset({RecoveryState.EXECUTING}),
    RecoveryState.EXECUTING: frozenset(
        {RecoveryState.EXECUTED, RecoveryState.COMPENSATING, RecoveryState.FAILED}
    ),
    RecoveryState.EXECUTED: frozenset({RecoveryState.RECOVERED, RecoveryState.FAILED}),
    RecoveryState.COMPENSATING: frozenset({RecoveryState.FAILED}),
    # Terminals — no transitions out.
    RecoveryState.RECOVERED: frozenset(),
    RecoveryState.FAILED: frozenset(),
    RecoveryState.ABANDONED: frozenset(),
}


def _recovery_key(transaction_id: TransactionId, attempt_number: int) -> str:
    """Deterministic per-attempt idempotency key (also used for gateway calls)."""
    raw = f"{transaction_id}:{attempt_number}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


@dataclass(slots=True)
class Recovery:
    """The recovery saga aggregate.

    Holds saga state, pointers to produced artifacts (diagnosis_id, ...) and
    a pending-events queue the repository drains during save.
    """

    id: RecoveryId
    tenant_id: TenantId
    transaction_id: TransactionId
    recovery_key: str
    state: RecoveryState = RecoveryState.CREATED

    diagnosis_id: DiagnosisId | None = None
    strategy_id: StrategyId | None = None
    risk_assessment_id: RiskAssessmentId | None = None
    policy_decision_id: PolicyDecisionId | None = None
    execution_attempt_id: ExecutionAttemptId | None = None

    recovered_amount_cents: int | None = None
    failure_reason: str | None = None

    version: int = 0
    _pending: list[DomainEvent] = field(default_factory=list, repr=False)

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------
    @classmethod
    def start(
        cls,
        *,
        recovery_id: RecoveryId,
        tenant_id: TenantId,
        transaction_id: TransactionId,
        attempt_number: int,
        metadata: EventMetadata | None = None,
    ) -> "Recovery":
        if attempt_number < 1:
            raise InvariantViolationError("attempt_number must be >= 1")
        recovery_key = _recovery_key(transaction_id, attempt_number)
        rec = cls(
            id=recovery_id,
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            recovery_key=recovery_key,
        )
        rec._apply(
            RecoveryCreated(
                tenant_id=tenant_id,
                recovery_id=recovery_id,
                transaction_id=transaction_id,
                recovery_key=recovery_key,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )
        return rec

    # -------------------------------------------------------------------------
    # Saga transitions
    # -------------------------------------------------------------------------
    def diagnose(
        self,
        *,
        diagnosis_id: DiagnosisId,
        root_cause_category: str,
        is_recoverable: bool,
        confidence: float,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.CREATED)
        if not 0 <= confidence <= 1:
            raise InvariantViolationError("diagnosis confidence must be in [0, 1]")
        self._apply(
            RecoveryDiagnosed(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                diagnosis_id=diagnosis_id,
                root_cause_category=root_cause_category,
                is_recoverable=is_recoverable,
                confidence=confidence,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def propose_strategy(
        self,
        *,
        strategy_id: StrategyId,
        strategy: RecoveryStrategy,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.DIAGNOSED)
        self._apply(
            RecoveryStrategyProposed(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                strategy_id=strategy_id,
                strategy=strategy,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def assess_risk(
        self,
        *,
        risk_assessment_id: RiskAssessmentId,
        overall_risk_level: str,
        duplicate_charge_probability: float,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.STRATEGY_PROPOSED)
        if not 0 <= duplicate_charge_probability <= 1:
            raise InvariantViolationError(
                "duplicate_charge_probability must be in [0, 1]"
            )
        self._apply(
            RecoveryRiskAssessed(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                risk_assessment_id=risk_assessment_id,
                overall_risk_level=overall_risk_level,
                duplicate_charge_probability=duplicate_charge_probability,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def evaluate_policy(
        self,
        *,
        policy_decision_id: PolicyDecisionId,
        outcome: PolicyOutcome,
        matched_rule_id: str | None,
        reason: str,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.RISK_ASSESSED)
        self._apply(
            RecoveryPolicyEvaluated(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                policy_decision_id=policy_decision_id,
                outcome=outcome,
                matched_rule_id=matched_rule_id,
                reason=reason,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

        # Follow-up event(s) derived from the policy outcome.
        if outcome == PolicyOutcome.REQUIRE_APPROVAL:
            self._apply(
                RecoveryApprovalRequested(
                    tenant_id=self.tenant_id,
                    recovery_id=self.id,
                    reason=reason,
                    metadata=metadata or EventMetadata(),
                ),
                record=True,
            )
        elif outcome == PolicyOutcome.DENY:
            self._apply(
                RecoveryFailed(
                    tenant_id=self.tenant_id,
                    recovery_id=self.id,
                    reason=f"Policy denied: {reason}",
                    metadata=metadata or EventMetadata(),
                ),
                record=True,
            )

    def approve(
        self,
        *,
        approver_id: str | None = None,
        note: str | None = None,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.AWAITING_APPROVAL)
        self._apply(
            RecoveryApproved(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                approver_id=approver_id,
                approval_note=note,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def reject(
        self,
        *,
        rejector_id: str | None = None,
        rejection_reason: str,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.AWAITING_APPROVAL)
        self._apply(
            RecoveryRejected(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                rejector_id=rejector_id,
                rejection_reason=rejection_reason,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def start_execution(
        self,
        *,
        execution_attempt_id: ExecutionAttemptId,
        gateway_id: str,
        idempotency_key: str,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.POLICY_EVALUATED, RecoveryState.APPROVED)
        self._apply(
            RecoveryExecutionStarted(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                execution_attempt_id=execution_attempt_id,
                gateway_id=gateway_id,
                idempotency_key=idempotency_key,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def complete_execution(
        self,
        *,
        outcome: ExecutionOutcome,
        decline_code: str | None = None,
        latency_ms: int | None = None,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.EXECUTING)
        if self.execution_attempt_id is None:
            raise InvariantViolationError(
                "complete_execution requires a prior start_execution"
            )
        self._apply(
            RecoveryExecutionCompleted(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                execution_attempt_id=self.execution_attempt_id,
                outcome=outcome,
                decline_code=decline_code,
                latency_ms=latency_ms,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def succeed(
        self,
        *,
        recovered_amount_cents: int,
        metadata: EventMetadata | None = None,
    ) -> None:
        self._require(RecoveryState.EXECUTED)
        if recovered_amount_cents <= 0:
            raise InvariantViolationError("recovered amount must be positive")
        self._apply(
            RecoverySucceeded(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                recovered_amount_cents=recovered_amount_cents,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def fail(self, *, reason: str, metadata: EventMetadata | None = None) -> None:
        if self.is_terminal:
            raise InvariantViolationError(
                f"Cannot fail terminal recovery (state={self.state})"
            )
        self._apply(
            RecoveryFailed(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                reason=reason,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    def abandon(self, *, reason: str, metadata: EventMetadata | None = None) -> None:
        if self.is_terminal:
            raise InvariantViolationError(
                f"Cannot abandon terminal recovery (state={self.state})"
            )
        self._apply(
            RecoveryAbandoned(
                tenant_id=self.tenant_id,
                recovery_id=self.id,
                reason=reason,
                metadata=metadata or EventMetadata(),
            ),
            record=True,
        )

    # -------------------------------------------------------------------------
    # Replay
    # -------------------------------------------------------------------------
    @classmethod
    def replay(cls, events: list[DomainEvent]) -> "Recovery":
        if not events:
            raise InvariantViolationError("Cannot replay empty event list")
        first = events[0]
        if not isinstance(first, RecoveryCreated):
            raise InvariantViolationError(
                f"First event must be RecoveryCreated, got {type(first).__name__}"
            )
        rec = cls(
            id=first.recovery_id,
            tenant_id=first.tenant_id,
            transaction_id=first.transaction_id,
            recovery_key=first.recovery_key,
        )
        for ev in events:
            rec._apply(ev, record=False)
            rec.version += 1
        return rec

    def pull_pending_events(self) -> list[DomainEvent]:
        out = list(self._pending)
        self._pending.clear()
        return out

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------
    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def _require(self, *allowed: RecoveryState) -> None:
        if self.state not in allowed:
            raise InvariantViolationError(
                f"Operation not allowed in state {self.state!r}; "
                f"expected one of {[s.value for s in allowed]}"
            )

    def _transition_to(self, new_state: RecoveryState) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise InvariantViolationError(
                f"Illegal transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    def _apply(self, event: DomainEvent, *, record: bool) -> None:
        match event:
            case RecoveryCreated():
                pass  # initial state already CREATED
            case RecoveryDiagnosed() as ev:
                self.diagnosis_id = ev.diagnosis_id
                self._transition_to(RecoveryState.DIAGNOSED)
            case RecoveryStrategyProposed() as ev:
                self.strategy_id = ev.strategy_id
                self._transition_to(RecoveryState.STRATEGY_PROPOSED)
            case RecoveryRiskAssessed() as ev:
                self.risk_assessment_id = ev.risk_assessment_id
                self._transition_to(RecoveryState.RISK_ASSESSED)
            case RecoveryPolicyEvaluated() as ev:
                self.policy_decision_id = ev.policy_decision_id
                self._transition_to(RecoveryState.POLICY_EVALUATED)
            case RecoveryApprovalRequested():
                self._transition_to(RecoveryState.AWAITING_APPROVAL)
            case RecoveryApproved():
                self._transition_to(RecoveryState.APPROVED)
            case RecoveryRejected() as ev:
                self.failure_reason = ev.rejection_reason
                self._transition_to(RecoveryState.FAILED)
            case RecoveryExecutionStarted() as ev:
                self.execution_attempt_id = ev.execution_attempt_id
                self._transition_to(RecoveryState.EXECUTING)
            case RecoveryExecutionCompleted() as ev:
                if ev.outcome == ExecutionOutcome.SUCCESS:
                    self._transition_to(RecoveryState.EXECUTED)
                else:
                    self._transition_to(RecoveryState.FAILED)
            case RecoverySucceeded() as ev:
                self.recovered_amount_cents = ev.recovered_amount_cents
                self._transition_to(RecoveryState.RECOVERED)
            case RecoveryFailed() as ev:
                self.failure_reason = ev.reason
                if self.state != RecoveryState.FAILED:
                    self._transition_to(RecoveryState.FAILED)
            case RecoveryAbandoned() as ev:
                self.failure_reason = ev.reason
                self._transition_to(RecoveryState.ABANDONED)
            case _:
                raise InvariantViolationError(
                    f"Unknown event in Recovery stream: {type(event).__name__}"
                )

        if record:
            self._pending.append(event)

    # Stable factory for fresh ID — repository uses this when starting.
    @staticmethod
    def new_id() -> RecoveryId:
        return RecoveryId(new_id())
