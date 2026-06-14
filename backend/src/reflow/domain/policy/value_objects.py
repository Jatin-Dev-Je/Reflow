"""Policy value objects — the language the policy engine speaks.

Three concepts:
    * PolicyContext   — typed input fed to the engine
    * PolicyOutcome   — what a rule decided (allow / deny / require_approval)
    * PolicyDecision  — the full decision record with reason + citations

The PolicyContext schema is intentionally narrow: the engine evaluates
deterministic predicates against well-typed fields. Anything that smells like
free-form (LLM scores, narrative explanations) goes in `agent_outputs` and
is treated as data, not as control flow.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import TenantId, TransactionId
from reflow.domain.audit import Citation
from reflow.domain.transactions import DeclineCategory


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class RecoveryStrategyKind(StrEnum):
    """Mirror of agent.strategy action_type, kept here so policies don't
    depend on the agent module."""

    IMMEDIATE_RETRY = "immediate_retry"
    DELAYED_RETRY = "delayed_retry"
    GATEWAY_REROUTE = "gateway_reroute"
    RAIL_SWITCH = "rail_switch"
    PAYMENT_LINK_NUDGE = "payment_link_nudge"
    GRACEFUL_FAILURE = "graceful_failure"
    MANUAL_REVIEW = "manual_review"


class PolicyContext(BaseModel):
    """Strict, typed inputs to policy evaluation.

    Everything in here is replay-safe: a historical context_snapshot can be
    fed back through the engine and produce the same decision deterministically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: TenantId
    transaction_id: TransactionId

    amount_cents: int = Field(gt=0)
    currency: str
    issuer_id: str | None = None
    gateway_id: str

    attempt_number: int = Field(ge=1, description="The next attempt number being proposed.")
    decline_category: DeclineCategory | None = None
    decline_code_normalized: str | None = None

    proposed_strategy: RecoveryStrategyKind
    proposed_delay_seconds: int | None = Field(default=None, ge=0)

    diagnosis_confidence: float | None = Field(default=None, ge=0, le=1)
    risk_level: str | None = None
    duplicate_charge_probability: float | None = Field(default=None, ge=0, le=1)
    expected_recovery_probability: float | None = Field(default=None, ge=0, le=1)

    # Tenant-configurable thresholds, snapshotted at evaluation time so we
    # can replay decisions deterministically.
    tenant_max_retries: int = Field(ge=0, le=100)
    tenant_high_value_threshold_cents: int = Field(gt=0)
    tenant_hitl_required_above_cents: int = Field(gt=0)

    # Free-form agent outputs — engine treats these as data only.
    agent_outputs: dict[str, Any] = Field(default_factory=dict)

    evaluated_at: datetime


class PolicyDecision(BaseModel):
    """The record produced by evaluating a policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: PolicyOutcome
    matched_rule_id: str | None = Field(
        default=None,
        description="Identifier of the rule that produced this outcome. "
        "None means 'default allow' — no rule matched.",
    )
    reason: str = Field(min_length=1, max_length=512)
    citations: list[Citation] = Field(default_factory=list)
    policy_version_id: UUID
    context_snapshot: dict[str, Any]
    decided_at: datetime
