"""StrategyAgent input + output schemas.

The agent picks one recovery action and justifies it with evidence pulled
from the diagnosis + historical patterns. Schema enforces:

    * exactly ONE strategy_kind (no waffling)
    * required rationale tied to evidence
    * expected_recovery_probability in [0, 1]
    * at least one evidence item — no claims without citations
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from reflow.agents.diagnosis.schemas import RootCauseCategory
from reflow.core.types import DiagnosisId, TransactionId
from reflow.domain.policy import RecoveryStrategyKind


class StrategyEvidenceItem(BaseModel):
    """One piece of evidence backing the strategy choice."""

    model_config = ConfigDict(extra="forbid")

    observation: str = Field(min_length=1, max_length=512)
    source_kind: str = Field(
        description="Where the agent saw it: 'pattern_match', 'historical_recovery', "
        "'issuer_health', 'gateway_health', or 'rule_match'.",
        min_length=1,
        max_length=64,
    )
    weight: float = Field(ge=0.0, le=1.0)


class StrategyInput(BaseModel):
    """What the agent knows when proposing a strategy."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: TransactionId
    diagnosis_id: DiagnosisId

    amount_cents: int = Field(gt=0)
    currency: str
    gateway_provider: str
    issuer_id: str | None = None

    root_cause_category: RootCauseCategory
    is_recoverable: bool
    diagnosis_confidence: float = Field(ge=0.0, le=1.0)

    # Memory signals — fed from intel.recovery_patterns when available.
    pattern_delayed_retry_success_rate: float | None = Field(default=None, ge=0, le=1)
    pattern_reroute_success_rate: float | None = Field(default=None, ge=0, le=1)
    pattern_payment_link_success_rate: float | None = Field(default=None, ge=0, le=1)
    pattern_avg_recovery_delay_seconds: int | None = Field(default=None, ge=0)

    # Available routing options.
    alternate_gateways: list[str] = Field(default_factory=list)

    # Tenant configuration constraints.
    max_delay_seconds: int = Field(default=86_400, gt=0)


class StrategyOutput(BaseModel):
    """The chosen strategy and the case for it."""

    model_config = ConfigDict(extra="forbid")

    strategy_kind: RecoveryStrategyKind
    delay_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Required when strategy_kind is delayed_retry.",
    )
    alternate_gateway: str | None = Field(
        default=None,
        description="Required when strategy_kind is gateway_reroute or rail_switch.",
    )

    expected_recovery_probability: float = Field(ge=0.0, le=1.0)
    expected_latency_seconds: int = Field(ge=0)

    rationale: str = Field(min_length=1, max_length=2048)
    evidence: list[StrategyEvidenceItem] = Field(min_length=1, max_length=20)
