"""GuardAgent input + output schemas.

Guard is a consistency checker. After Diagnosis + Strategy + Risk + Policy
have all produced outputs, Guard inspects the FULL picture to catch internal
contradictions an individual agent would miss — for example, a strategy
that contradicts the diagnosis's recoverability flag, or risk scores
inconsistent with the diagnosis confidence.

Guard NEVER overrides a policy deny. It can only:
    * APPROVE   — everything looks coherent, proceed.
    * HOLD      — surface for human review (logged but not blocking by default).
    * BLOCK     — final safety net; halts execution.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from reflow.agents.diagnosis.schemas import RootCauseCategory
from reflow.agents.risk.schemas import RiskLevel
from reflow.core.types import (
    DiagnosisId,
    PolicyDecisionId,
    RiskAssessmentId,
    StrategyId,
    TransactionId,
)
from reflow.domain.policy import PolicyOutcome, RecoveryStrategyKind


class GuardOutcome(StrEnum):
    APPROVE = "approve"
    HOLD = "hold"
    BLOCK = "block"


class GuardConcern(BaseModel):
    """A specific inconsistency or risk Guard noticed."""

    model_config = ConfigDict(extra="forbid")

    severity: str = Field(
        description="'info', 'warning', or 'blocker' — only 'blocker' "
        "should drive a BLOCK outcome.",
    )
    observation: str = Field(min_length=1, max_length=512)
    source_kind: str = Field(min_length=1, max_length=64)


class GuardInput(BaseModel):
    """The full upstream context Guard inspects."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: TransactionId
    diagnosis_id: DiagnosisId
    strategy_id: StrategyId
    risk_assessment_id: RiskAssessmentId
    policy_decision_id: PolicyDecisionId

    # Diagnosis facts.
    root_cause_category: RootCauseCategory
    is_recoverable: bool
    diagnosis_confidence: float = Field(ge=0.0, le=1.0)

    # Strategy facts.
    strategy_kind: RecoveryStrategyKind
    strategy_expected_recovery_probability: float = Field(ge=0.0, le=1.0)
    strategy_delay_seconds: int | None = None
    strategy_alternate_gateway: str | None = None

    # Risk facts.
    overall_risk_level: RiskLevel
    duplicate_charge_probability: float = Field(ge=0.0, le=1.0)
    financial_risk_score: float = Field(ge=0.0, le=1.0)
    customer_friction_score: float = Field(ge=0.0, le=1.0)

    # Policy outcome (Guard cannot override deny).
    policy_outcome: PolicyOutcome
    policy_matched_rule_id: str | None = None
    policy_reason: str


class GuardOutput(BaseModel):
    """Guard's final verdict."""

    model_config = ConfigDict(extra="forbid")

    outcome: GuardOutcome
    rationale: str = Field(min_length=1, max_length=2048)
    concerns: list[GuardConcern] = Field(default_factory=list, max_length=20)
