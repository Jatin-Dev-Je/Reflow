"""Retry-limit rule — denies attempts beyond the tenant's configured max."""

from __future__ import annotations

from datetime import UTC, datetime

from reflow.domain.audit import Citation, CitationSource, EvidenceType
from reflow.domain.policy import PolicyContext, PolicyOutcome
from reflow.infrastructure.policy_engine.evaluator import Rule


def _exceeds_retry_budget(ctx: PolicyContext) -> bool:
    return ctx.attempt_number > ctx.tenant_max_retries


def _deny(ctx: PolicyContext) -> tuple[PolicyOutcome, str, list[Citation]]:
    reason = (
        f"Proposed attempt #{ctx.attempt_number} exceeds tenant retry budget "
        f"of {ctx.tenant_max_retries}"
    )
    citation = Citation(
        index=1,
        evidence_type=EvidenceType.RULE_MATCH,
        source=CitationSource(
            source_table="core.tenant_settings",
            source_query={"tenant_id": str(ctx.tenant_id), "field": "max_retries_per_txn"},
        ),
        observation=f"Tenant retry budget = {ctx.tenant_max_retries}",
        data={
            "max_retries_per_txn": ctx.tenant_max_retries,
            "attempt_number": ctx.attempt_number,
        },
        weight=1.0,
        observed_at=datetime.now(UTC),
    )
    return PolicyOutcome.DENY, reason, [citation]


retry_limit_rule = Rule(
    id="retry_limit.exceeded",
    description="Deny any recovery attempt beyond the tenant's configured retry budget.",
    when=_exceeds_retry_budget,
    decide=_deny,
)
