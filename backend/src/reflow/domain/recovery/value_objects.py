"""Recovery value objects — the saga state machine and execution metadata.

The state machine is *small on purpose*: every transition is a domain event,
so the audit trail is automatic. Adding states means adding events; we don't
let states accumulate implicit transitions.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from reflow.domain.policy import RecoveryStrategyKind


class RecoveryState(StrEnum):
    """States of a recovery saga.

    Terminal states: RECOVERED, FAILED, ABANDONED.
    Everything else is a checkpoint the saga driver can resume from.
    """

    CREATED = "created"
    DIAGNOSED = "diagnosed"
    STRATEGY_PROPOSED = "strategy_proposed"
    RISK_ASSESSED = "risk_assessed"
    POLICY_EVALUATED = "policy_evaluated"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    COMPENSATING = "compensating"
    RECOVERED = "recovered"
    FAILED = "failed"
    ABANDONED = "abandoned"


TERMINAL_STATES = frozenset(
    {RecoveryState.RECOVERED, RecoveryState.FAILED, RecoveryState.ABANDONED}
)


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


class RecoveryStrategy(BaseModel):
    """A proposed (or chosen) recovery strategy. Mirrors the agent output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: RecoveryStrategyKind
    parameters: dict = Field(default_factory=dict)
    expected_recovery_probability: float | None = Field(default=None, ge=0, le=1)
    expected_revenue_cents: int | None = None
    expected_latency_seconds: int | None = None
    rationale: str | None = None
