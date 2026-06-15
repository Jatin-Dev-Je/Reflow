"""RiskAgent input + output schemas.

The agent scores four independent risk dimensions, rolls them up to an
overall level, and supplies citation-backed factors. The duplicate_charge_
probability is the single most important output — the policy engine reads
it in `duplicate_prevention_rule` to block execution.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import StrategyId, TransactionId
from reflow.domain.policy import RecoveryStrategyKind


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactor(BaseModel):
    """One contributing factor to a risk score."""

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(
        description="Which risk dimension this factor belongs to: "
        "'financial', 'operational', 'customer_friction', or 'duplicate_charge'.",
    )
    observation: str = Field(min_length=1, max_length=512)
    contribution: float = Field(
        ge=0.0,
        le=1.0,
        description="How much this factor pushes the risk up (1.0 = max push).",
    )
    source_kind: str = Field(min_length=1, max_length=64)


class RiskInput(BaseModel):
    """Everything the risk agent needs to know."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: TransactionId
    strategy_id: StrategyId

    amount_cents: int = Field(gt=0)
    currency: str
    proposed_strategy: RecoveryStrategyKind

    # Recent attempt context.
    attempt_number: int = Field(ge=1)
    previous_attempts_failed: int = Field(ge=0)

    # Health signals.
    gateway_recent_success_rate: float | None = Field(default=None, ge=0, le=1)
    issuer_recent_success_rate: float | None = Field(default=None, ge=0, le=1)

    # History.
    historical_dup_charge_rate_for_strategy: float | None = Field(default=None, ge=0, le=1)

    # Strategy details we need to assess.
    strategy_changes_gateway: bool = False
    strategy_delay_seconds: int | None = Field(default=None, ge=0)


class RiskOutput(BaseModel):
    """Multi-dimensional risk assessment."""

    model_config = ConfigDict(extra="forbid")

    financial_risk_score: float = Field(ge=0.0, le=1.0)
    operational_risk_score: float = Field(ge=0.0, le=1.0)
    customer_friction_score: float = Field(ge=0.0, le=1.0)
    duplicate_charge_probability: float = Field(ge=0.0, le=1.0)

    overall_risk_level: RiskLevel

    expected_revenue_impact_cents: int | None = None
    rationale: str = Field(min_length=1, max_length=2048)
    factors: list[RiskFactor] = Field(min_length=1, max_length=20)
