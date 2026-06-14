"""High-value approval rule — large transactions require human sign-off."""

from __future__ import annotations

from datetime import UTC, datetime

from reflow.domain.audit import Citation, CitationSource, EvidenceType
from reflow.domain.policy import PolicyContext, PolicyOutcome
from reflow.infrastructure.policy_engine.evaluator import Rule


def _requires_approval(ctx: PolicyContext) -> bool:
    return ctx.amount_cents >= ctx.tenant_hitl_required_above_cents


def _ask_human(ctx: PolicyContext) -> tuple[PolicyOutcome, str, list[Citation]]:
    reason = (
        f"Transaction value {ctx.amount_cents / 100:.2f} {ctx.currency} "
        f"meets HITL threshold {ctx.tenant_hitl_required_above_cents / 100:.2f}"
    )
    citation = Citation(
        index=1,
        evidence_type=EvidenceType.RULE_MATCH,
        source=CitationSource(
            source_table="core.tenant_settings",
            source_query={"tenant_id": str(ctx.tenant_id), "field": "hitl_required_above_cents"},
        ),
        observation=(
            f"HITL threshold = {ctx.tenant_hitl_required_above_cents} cents; "
            f"amount = {ctx.amount_cents} cents"
        ),
        data={
            "amount_cents": ctx.amount_cents,
            "currency": ctx.currency,
            "hitl_required_above_cents": ctx.tenant_hitl_required_above_cents,
        },
        weight=1.0,
        observed_at=datetime.now(UTC),
    )
    return PolicyOutcome.REQUIRE_APPROVAL, reason, [citation]


high_value_rule = Rule(
    id="high_value.requires_approval",
    description="Send recoveries for very high-value transactions through HITL approval.",
    when=_requires_approval,
    decide=_ask_human,
)
