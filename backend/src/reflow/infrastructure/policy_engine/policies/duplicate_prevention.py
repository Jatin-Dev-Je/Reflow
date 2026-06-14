"""Duplicate-prevention rule — deny if the risk model flags a high
double-charge probability.

This is one of three independent layers preventing double charges (see
ADR-0005). At the gateway layer we have the UNIQUE constraint; here we
catch the risk *before* a gateway call is made when the model warns.
"""

from __future__ import annotations

from datetime import UTC, datetime

from reflow.domain.audit import Citation, CitationSource, EvidenceType
from reflow.domain.policy import PolicyContext, PolicyOutcome
from reflow.infrastructure.policy_engine.evaluator import Rule

# Threshold above which the Risk Agent's duplicate-charge probability blocks execution.
DUPLICATE_CHARGE_THRESHOLD = 0.10


def _duplicate_risk_too_high(ctx: PolicyContext) -> bool:
    p = ctx.duplicate_charge_probability
    return p is not None and p >= DUPLICATE_CHARGE_THRESHOLD


def _deny(ctx: PolicyContext) -> tuple[PolicyOutcome, str, list[Citation]]:
    p = ctx.duplicate_charge_probability or 0.0
    reason = (
        f"Risk Agent flagged duplicate-charge probability {p:.2%} "
        f"(threshold {DUPLICATE_CHARGE_THRESHOLD:.0%})"
    )
    citation = Citation(
        index=1,
        evidence_type=EvidenceType.RULE_MATCH,
        source=CitationSource(
            source_table="agent.risk_assessments",
            source_query={"transaction_id": str(ctx.transaction_id)},
        ),
        observation=f"duplicate_charge_probability = {p:.4f}",
        data={
            "duplicate_charge_probability": p,
            "threshold": DUPLICATE_CHARGE_THRESHOLD,
        },
        weight=1.0,
        observed_at=datetime.now(UTC),
    )
    return PolicyOutcome.DENY, reason, [citation]


duplicate_prevention_rule = Rule(
    id="duplicate_prevention.high_risk",
    description="Deny execution when the risk model warns of a high duplicate-charge probability.",
    when=_duplicate_risk_too_high,
    decide=_deny,
)
