"""Project coordinator-produced agent outputs into read-model tables.

Called by StartRecoveryChainHandler after the coordinator finishes. Each
artifact is inserted as a single row + child rows where applicable (e.g.
diagnosis -> evidence_items). Idempotent on the artifact ID — re-running
the same chain on a saved recovery doesn't double-insert.

Telemetry (agent_run_id, prompt template hash, provider chain, tokens, cost)
is captured on each row via the agent_run_id + llm_provider/llm_model
columns. The full obs.agent_runs + obs.llm_calls trail comes when those
tables are wired (TODO — currently lives only in step records).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.agents.diagnosis.schemas import DiagnosisOutput
from reflow.agents.risk.schemas import RiskOutput
from reflow.agents.strategy.schemas import StrategyOutput
from reflow.core.observability.logging import get_logger
from reflow.core.types import (
    AttemptId,
    DiagnosisId,
    PolicyDecisionId,
    RecoveryId,
    RiskAssessmentId,
    StrategyId,
    TenantId,
    TransactionId,
)
from reflow.infrastructure.persistence.models import (
    DiagnosisModel,
    EvidenceItemModel,
    PolicyDecisionModel,
    RiskAssessmentModel,
    StrategyModel,
)

_logger = get_logger(__name__)


async def project_chain_outputs(
    session: AsyncSession,
    *,
    tenant_id: TenantId,
    transaction_id: TransactionId,
    attempt_id: AttemptId,
    recovery_id: RecoveryId,
    produced: dict[str, Any],
) -> None:
    """Persist diagnosis / strategy / risk / policy outputs from a coordinator run.

    Missing keys are skipped — partial chains (e.g. halted at policy_denied)
    produce only the artifacts that ran.
    """
    if "diagnosis" in produced:
        await _project_diagnosis(
            session,
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            attempt_id=attempt_id,
            artifact=produced["diagnosis"],
        )

    if "strategy" in produced:
        await _project_strategy(
            session,
            tenant_id=tenant_id,
            artifact=produced["strategy"],
            diagnosis_id=produced["diagnosis"]["id"],
        )

    if "risk" in produced:
        await _project_risk(
            session,
            tenant_id=tenant_id,
            artifact=produced["risk"],
            strategy_id=produced["strategy"]["id"],
        )

    if "policy" in produced:
        await _project_policy(
            session,
            tenant_id=tenant_id,
            artifact=produced["policy"],
            recovery_id=recovery_id,
            strategy_id=produced.get("strategy", {}).get("id"),
        )


async def _project_diagnosis(
    session: AsyncSession,
    *,
    tenant_id: TenantId,
    transaction_id: TransactionId,
    attempt_id: AttemptId,
    artifact: dict[str, Any],
) -> None:
    diag_id: DiagnosisId = artifact["id"]
    output: DiagnosisOutput = artifact["output"]
    telemetry = artifact["telemetry"]

    provider_chain = list(telemetry.provider_chain) if telemetry.provider_chain else []
    llm_provider = provider_chain[-1] if provider_chain else None

    insert_stmt = pg_insert(DiagnosisModel).values(
        id=diag_id,
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        attempt_id=attempt_id,
        root_cause=output.root_cause,
        root_cause_category=output.root_cause_category.value,
        is_recoverable=output.is_recoverable,
        confidence=output.confidence,
        agent_run_id=telemetry.agent_run_id,
        llm_provider=llm_provider,
        llm_model=None,  # set when llm_calls table is wired
        reasoning=output.reasoning,
    )
    insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=[DiagnosisModel.id])
    await session.execute(insert_stmt)

    # Evidence items — each EvidenceItem becomes a citation row.
    now = datetime.now(UTC)
    for idx, item in enumerate(output.evidence, start=1):
        ev_stmt = pg_insert(EvidenceItemModel).values(
            diagnosis_id=diag_id,
            citation_index=idx,
            evidence_type=_map_evidence_type(item.source_kind),
            source_table=_map_source_table(item.source_kind),
            source_query=None,
            observation=item.observation,
            data={"weight": item.weight, "source_kind": item.source_kind},
            weight=item.weight,
            observed_at=now,
        )
        ev_stmt = ev_stmt.on_conflict_do_nothing(
            index_elements=[
                EvidenceItemModel.diagnosis_id,
                EvidenceItemModel.citation_index,
            ]
        )
        await session.execute(ev_stmt)


def _map_evidence_type(source_kind: str) -> str:
    """Coerce free-form source_kind from the LLM to the CHECK-allowed set."""
    allowed = {
        "historical_recovery",
        "gateway_health",
        "issuer_health",
        "pattern_match",
        "similar_failure",
        "rule_match",
        "external_signal",
    }
    return source_kind if source_kind in allowed else "external_signal"


def _map_source_table(source_kind: str) -> str | None:
    return {
        "gateway_health": "health.gateway_snapshots",
        "issuer_health": "health.issuer_snapshots",
        "pattern_match": "intel.recovery_patterns",
        "historical_recovery": "intel.recovery_episodes",
        "similar_failure": "intel.failure_embeddings",
        "rule_match": "policy.policy_versions",
    }.get(source_kind)


async def _project_strategy(
    session: AsyncSession,
    *,
    tenant_id: TenantId,
    artifact: dict[str, Any],
    diagnosis_id: DiagnosisId,
) -> None:
    strategy_id: StrategyId = artifact["id"]
    output: StrategyOutput = artifact["output"]
    telemetry = artifact["telemetry"]

    parameters: dict[str, Any] = {}
    if output.delay_seconds is not None:
        parameters["delay_seconds"] = output.delay_seconds
    if output.alternate_gateway is not None:
        parameters["alternate_gateway"] = output.alternate_gateway

    stmt = pg_insert(StrategyModel).values(
        id=strategy_id,
        tenant_id=tenant_id,
        diagnosis_id=diagnosis_id,
        action_type=output.strategy_kind.value,
        parameters=parameters,
        expected_recovery_probability=output.expected_recovery_probability,
        expected_revenue_cents=None,
        expected_latency_seconds=output.expected_latency_seconds,
        rationale=output.rationale,
        agent_run_id=telemetry.agent_run_id,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[StrategyModel.id])
    await session.execute(stmt)


async def _project_risk(
    session: AsyncSession,
    *,
    tenant_id: TenantId,
    artifact: dict[str, Any],
    strategy_id: StrategyId,
) -> None:
    risk_id: RiskAssessmentId = artifact["id"]
    output: RiskOutput = artifact["output"]
    telemetry = artifact["telemetry"]

    factors_json = [f.model_dump(mode="json") for f in output.factors]

    stmt = pg_insert(RiskAssessmentModel).values(
        id=risk_id,
        tenant_id=tenant_id,
        strategy_id=strategy_id,
        financial_risk_score=output.financial_risk_score,
        operational_risk_score=output.operational_risk_score,
        customer_friction_score=output.customer_friction_score,
        duplicate_charge_probability=output.duplicate_charge_probability,
        overall_risk_level=output.overall_risk_level.value,
        expected_revenue_impact_cents=output.expected_revenue_impact_cents,
        factors={"items": factors_json, "rationale": output.rationale},
        agent_run_id=telemetry.agent_run_id,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[RiskAssessmentModel.id])
    await session.execute(stmt)


async def _project_policy(
    session: AsyncSession,
    *,
    tenant_id: TenantId,
    artifact: dict[str, Any],
    recovery_id: RecoveryId,
    strategy_id: StrategyId | None,
) -> None:
    decision_id: PolicyDecisionId = artifact["id"]
    decision = artifact["decision"]

    citations_json = [c.model_dump(mode="json") for c in decision.citations] or None

    stmt = pg_insert(PolicyDecisionModel).values(
        id=decision_id,
        tenant_id=tenant_id,
        recovery_id=recovery_id,
        strategy_id=strategy_id,
        policy_version_id=decision.policy_version_id,
        decision=decision.outcome.value,
        matched_rule_id=decision.matched_rule_id,
        reason=decision.reason,
        citations=citations_json,
        context_snapshot=decision.context_snapshot,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[PolicyDecisionModel.id])
    await session.execute(stmt)
