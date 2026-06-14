"""Reroute-safety rule — block gateway_reroute when diagnosis confidence is low.

Re-routing a transaction to a different gateway is a real-money decision: the
new gateway will charge again. We require high confidence that the original
decline is *gateway-side*, not issuer-side, before rerouting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from reflow.domain.audit import Citation, CitationSource, EvidenceType
from reflow.domain.policy import PolicyContext, PolicyOutcome, RecoveryStrategyKind
from reflow.infrastructure.policy_engine.evaluator import Rule

MIN_REROUTE_CONFIDENCE = 0.80


def _reroute_with_low_confidence(ctx: PolicyContext) -> bool:
    if ctx.proposed_strategy != RecoveryStrategyKind.GATEWAY_REROUTE:
        return False
    return (ctx.diagnosis_confidence or 0.0) < MIN_REROUTE_CONFIDENCE


def _deny(ctx: PolicyContext) -> tuple[PolicyOutcome, str, list[Citation]]:
    confidence = ctx.diagnosis_confidence or 0.0
    reason = (
        f"Gateway reroute requires diagnosis_confidence >= {MIN_REROUTE_CONFIDENCE:.2f}; "
        f"got {confidence:.2f}"
    )
    citation = Citation(
        index=1,
        evidence_type=EvidenceType.RULE_MATCH,
        source=CitationSource(
            source_table="agent.diagnoses",
            source_query={"transaction_id": str(ctx.transaction_id)},
        ),
        observation=f"diagnosis_confidence = {confidence:.4f}",
        data={
            "diagnosis_confidence": confidence,
            "minimum_required": MIN_REROUTE_CONFIDENCE,
            "proposed_strategy": ctx.proposed_strategy.value,
        },
        weight=1.0,
        observed_at=datetime.now(UTC),
    )
    return PolicyOutcome.DENY, reason, [citation]


reroute_safety_rule = Rule(
    id="reroute_safety.low_confidence",
    description="Block gateway reroutes when diagnosis confidence is below threshold.",
    when=_reroute_with_low_confidence,
    decide=_deny,
)
