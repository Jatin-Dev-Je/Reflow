"""DiagnosisAgent input + output schemas.

Output is strictly validated. Required: root cause category, recoverable flag,
confidence, reasoning, AND at least one citation. An LLM that returns claims
without citations is treated the same as malformed output — repaired or
rejected.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import TransactionId
from reflow.domain.transactions import DeclineCategory


class RootCauseCategory(StrEnum):
    """Mirror of agent.diagnoses.root_cause_category check constraint."""

    ISSUER_OUTAGE = "issuer_outage"
    ISSUER_DECLINE = "issuer_decline"
    GATEWAY_DEGRADED = "gateway_degraded"
    GATEWAY_OUTAGE = "gateway_outage"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    FRAUD_SIGNAL = "fraud_signal"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    OTHER = "other"


class EvidenceItem(BaseModel):
    """A single piece of evidence the agent saw — becomes a Citation."""

    model_config = ConfigDict(extra="forbid")

    observation: str = Field(min_length=1, max_length=512)
    source_kind: str = Field(
        description="What source the evidence came from: 'gateway_health', "
        "'issuer_health', 'pattern_match', 'similar_failure', or 'rule_match'.",
        min_length=1,
        max_length=64,
    )
    weight: float = Field(ge=0.0, le=1.0)


class DiagnosisInput(BaseModel):
    """What the agent is shown about a failure."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: TransactionId
    amount_cents: int = Field(gt=0)
    currency: str
    gateway_provider: str
    issuer_id: str | None = None
    card_bin: str | None = None
    decline_code: str | None = None
    decline_category: DeclineCategory | None = None
    decline_message: str | None = None  # sanitized before substitution

    gateway_recent_success_rate: float | None = Field(default=None, ge=0, le=1)
    issuer_recent_success_rate: float | None = Field(default=None, ge=0, le=1)
    similar_failures_last_24h: int = Field(default=0, ge=0)
    recent_recovery_success_rate: float | None = Field(default=None, ge=0, le=1)


class DiagnosisOutput(BaseModel):
    """What the agent MUST return.

    Strict shape — extra fields rejected. At least one evidence item required
    so every claim is citable.
    """

    model_config = ConfigDict(extra="forbid")

    root_cause: str = Field(min_length=1, max_length=512)
    root_cause_category: RootCauseCategory
    is_recoverable: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=2048)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=20)
