"""Recovery agent coordinator — chains Diagnosis -> Strategy -> Risk -> Policy -> Guard.

This is the synchronous orchestration of the saga. In production the saga
driver process picks up `recovery.recoveries` rows where `next_action_at <=
now()` and runs this coordinator one transition at a time. For the demo we
expose a synchronous `run_full` that walks every step in a single call so
the API can show end-to-end behaviour without a background worker.

Each step:
    1. Resolves the inputs for the agent from the recovery's current state +
       prior outputs + memory signals.
    2. Calls the agent (LLM-backed).
    3. Mutates the Recovery aggregate, which records the appropriate event.
    4. Persists the artifact ID + telemetry alongside the event stream.

Failure semantics:
    * Agent raises -> recovery.fail(reason); chain stops.
    * Policy denies -> recovery.evaluate_policy emits PolicyEvaluated +
      RecoveryFailed; chain stops at policy_evaluated.
    * Policy requires_approval -> chain stops at awaiting_approval; the
      Approval API drives the resume.
    * Guard blocks -> recovery.fail; chain stops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from reflow.agents.diagnosis.agent import DiagnosisAgent
from reflow.agents.diagnosis.schemas import DiagnosisInput, DiagnosisOutput
from reflow.agents.guard.agent import GuardAgent
from reflow.agents.guard.schemas import GuardInput, GuardOutcome
from reflow.agents.risk.agent import RiskAgent
from reflow.agents.risk.schemas import RiskInput, RiskOutput
from reflow.agents.strategy.agent import StrategyAgent
from reflow.agents.strategy.schemas import StrategyInput, StrategyOutput
from reflow.core.events.event import EventMetadata
from reflow.core.observability.logging import get_logger
from reflow.core.types import (
    CorrelationId,
    DiagnosisId,
    PolicyDecisionId,
    RiskAssessmentId,
    StrategyId,
    new_correlation_id,
    new_id,
)
from reflow.domain.policy import (
    PolicyContext,
    PolicyOutcome,
    RecoveryStrategyKind,
)
from reflow.domain.recovery import (
    Recovery,
    RecoveryState,
    RecoveryStrategy,
)
from reflow.infrastructure.policy_engine import (
    PolicyEvaluator,
    build_default_policy,
)

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CoordinatorContext:
    """The static inputs the orchestrator needs to run a recovery.

    These come from the transaction read model + tenant settings + memory
    queries. The orchestrator does not query the DB itself — callers prepare
    a CoordinatorContext and hand it in.
    """

    amount_cents: int
    currency: str
    gateway_provider: str
    issuer_id: str | None
    card_bin: str | None
    decline_code: str | None
    decline_category_value: str | None
    decline_message: str | None

    # Health signals.
    gateway_recent_success_rate: float | None = None
    issuer_recent_success_rate: float | None = None
    similar_failures_last_24h: int = 0
    recent_recovery_success_rate: float | None = None

    # Pattern memory.
    pattern_delayed_retry_success_rate: float | None = None
    pattern_reroute_success_rate: float | None = None
    pattern_payment_link_success_rate: float | None = None
    pattern_avg_recovery_delay_seconds: int | None = None
    historical_dup_charge_rate_for_strategy: float | None = None

    alternate_gateways: tuple[str, ...] = ()

    # Tenant constraints (from core.tenant_settings).
    tenant_max_retries: int = 3
    tenant_high_value_threshold_cents: int = 5_000_000
    tenant_hitl_required_above_cents: int = 100_000_000
    max_delay_seconds: int = 86_400

    # Attempt context.
    attempt_number: int = 1
    previous_attempts_failed: int = 0


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One step in a coordinator run — surfaced for telemetry persistence."""

    name: str
    artifact_id: str | None
    telemetry: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CoordinatorResult:
    """Outcome of run_full. The recovery aggregate is mutated in place; this
    is for telemetry + control flow."""

    final_state: RecoveryState
    steps: list[StepRecord]
    stopped_reason: str | None = None  # why we halted before terminal success

    # Raw produced artifacts the handler projects to read-model tables.
    # Keys: 'diagnosis', 'strategy', 'risk', 'policy', 'guard'.
    produced: dict[str, Any] = field(default_factory=dict)


class RecoveryCoordinator:
    """Run the agent chain against a Recovery aggregate."""

    def __init__(
        self,
        *,
        diagnosis: DiagnosisAgent,
        strategy: StrategyAgent,
        risk: RiskAgent,
        guard: GuardAgent,
    ) -> None:
        self._diagnosis = diagnosis
        self._strategy = strategy
        self._risk = risk
        self._guard = guard

    async def run_full(
        self,
        *,
        recovery: Recovery,
        ctx: CoordinatorContext,
        correlation_id: CorrelationId | None = None,
    ) -> CoordinatorResult:
        corr = correlation_id or new_correlation_id()
        steps: list[StepRecord] = []
        produced: dict[str, Any] = {}

        # ----------------------------------------------------------- DIAGNOSIS
        try:
            diag = await self._diagnosis.run(
                tenant_id=recovery.tenant_id,
                inputs=self._build_diagnosis_input(recovery, ctx),
            )
        except Exception as exc:  # noqa: BLE001 — agent failure halts chain
            return self._fail(recovery, steps, "diagnosis_failed", str(exc))

        diagnosis_id = DiagnosisId(new_id())
        recovery.diagnose(
            diagnosis_id=diagnosis_id,
            root_cause_category=diag.output.root_cause_category.value,
            is_recoverable=diag.output.is_recoverable,
            confidence=diag.output.confidence,
            metadata=self._meta(corr, "agent:diagnosis"),
        )
        steps.append(_step("diagnosis", diagnosis_id, diag.telemetry))
        produced["diagnosis"] = {
            "id": diagnosis_id,
            "output": diag.output,
            "telemetry": diag.telemetry,
        }

        if not diag.output.is_recoverable:
            recovery.abandon(
                reason=f"Not recoverable: {diag.output.root_cause_category.value}",
                metadata=self._meta(corr, "agent:diagnosis"),
            )
            return CoordinatorResult(
                final_state=recovery.state,
                steps=steps,
                stopped_reason="not_recoverable",
                produced=produced,
            )

        # ------------------------------------------------------------ STRATEGY
        try:
            strat = await self._strategy.run(
                tenant_id=recovery.tenant_id,
                inputs=self._build_strategy_input(recovery, ctx, diag.output, diagnosis_id),
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(recovery, steps, "strategy_failed", str(exc))

        strategy_id = StrategyId(new_id())
        recovery.propose_strategy(
            strategy_id=strategy_id,
            strategy=RecoveryStrategy(
                kind=strat.output.strategy_kind,
                parameters=_strategy_params(strat.output),
                expected_recovery_probability=strat.output.expected_recovery_probability,
                expected_latency_seconds=strat.output.expected_latency_seconds,
                rationale=strat.output.rationale,
            ),
            metadata=self._meta(corr, "agent:strategy"),
        )
        steps.append(_step("strategy", strategy_id, strat.telemetry))
        produced["strategy"] = {
            "id": strategy_id,
            "output": strat.output,
            "telemetry": strat.telemetry,
        }

        # ---------------------------------------------------------------- RISK
        try:
            risk = await self._risk.run(
                tenant_id=recovery.tenant_id,
                inputs=self._build_risk_input(recovery, ctx, strat.output, strategy_id),
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(recovery, steps, "risk_failed", str(exc))

        risk_assessment_id = RiskAssessmentId(new_id())
        recovery.assess_risk(
            risk_assessment_id=risk_assessment_id,
            overall_risk_level=risk.output.overall_risk_level.value,
            duplicate_charge_probability=risk.output.duplicate_charge_probability,
            metadata=self._meta(corr, "agent:risk"),
        )
        steps.append(_step("risk", risk_assessment_id, risk.telemetry))
        produced["risk"] = {
            "id": risk_assessment_id,
            "output": risk.output,
            "telemetry": risk.telemetry,
        }

        # ------------------------------------------------------------- POLICY
        policy_ctx = self._build_policy_context(recovery, ctx, strat.output, risk.output)
        policy_decision = PolicyEvaluator(build_default_policy()).evaluate(policy_ctx)
        policy_decision_id = PolicyDecisionId(new_id())
        recovery.evaluate_policy(
            policy_decision_id=policy_decision_id,
            outcome=policy_decision.outcome,
            matched_rule_id=policy_decision.matched_rule_id,
            reason=policy_decision.reason,
            metadata=self._meta(corr, "policy:engine"),
        )
        steps.append(
            StepRecord(
                name="policy",
                artifact_id=str(policy_decision_id),
                telemetry={
                    "outcome": policy_decision.outcome.value,
                    "matched_rule_id": policy_decision.matched_rule_id,
                    "reason": policy_decision.reason,
                    "policy_version_id": str(policy_decision.policy_version_id),
                    "citations": [
                        c.model_dump(mode="json") for c in policy_decision.citations
                    ],
                },
            )
        )
        produced["policy"] = {
            "id": policy_decision_id,
            "decision": policy_decision,
        }

        if policy_decision.outcome == PolicyOutcome.DENY:
            return CoordinatorResult(
                final_state=recovery.state,
                steps=steps,
                stopped_reason="policy_denied",
                produced=produced,
            )
        if policy_decision.outcome == PolicyOutcome.REQUIRE_APPROVAL:
            return CoordinatorResult(
                final_state=recovery.state,
                steps=steps,
                stopped_reason="awaiting_approval",
                produced=produced,
            )

        # -------------------------------------------------------------- GUARD
        try:
            guard = await self._guard.run(
                tenant_id=recovery.tenant_id,
                inputs=self._build_guard_input(
                    recovery,
                    diag.output,
                    diagnosis_id,
                    strat.output,
                    strategy_id,
                    risk.output,
                    risk_assessment_id,
                    policy_decision_id,
                    policy_decision.outcome,
                    policy_decision.matched_rule_id,
                    policy_decision.reason,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(recovery, steps, "guard_failed", str(exc))

        steps.append(_step("guard", None, guard.telemetry))
        produced["guard"] = {"output": guard.output, "telemetry": guard.telemetry}

        if guard.output.outcome == GuardOutcome.BLOCK:
            recovery.fail(
                reason=f"Guard blocked: {guard.output.rationale}",
                metadata=self._meta(corr, "agent:guard"),
            )
            return CoordinatorResult(
                final_state=recovery.state,
                steps=steps,
                stopped_reason="guard_blocked",
                produced=produced,
            )
        if guard.output.outcome == GuardOutcome.HOLD:
            return CoordinatorResult(
                final_state=recovery.state,
                steps=steps,
                stopped_reason="guard_hold",
                produced=produced,
            )

        # ----------------------------------------------------- READY TO EXECUTE
        # We stop here. Actual gateway execution happens in a separate step so
        # the demo can show the chain reaching POLICY_EVALUATED + Guard
        # approved before any money moves.
        return CoordinatorResult(
            final_state=recovery.state,
            steps=steps,
            stopped_reason="ready_to_execute",
            produced=produced,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _meta(corr: CorrelationId, source: str) -> EventMetadata:
        return EventMetadata(correlation_id=corr, source=source)

    @staticmethod
    def _fail(
        recovery: Recovery,
        steps: list[StepRecord],
        stopped_reason: str,
        error: str,
    ) -> CoordinatorResult:
        recovery.fail(reason=f"{stopped_reason}: {error}")
        return CoordinatorResult(
            final_state=recovery.state, steps=steps, stopped_reason=stopped_reason
        )

    def _build_diagnosis_input(
        self, recovery: Recovery, ctx: CoordinatorContext
    ) -> DiagnosisInput:
        from reflow.domain.transactions import DeclineCategory

        cat = (
            DeclineCategory(ctx.decline_category_value)
            if ctx.decline_category_value
            else None
        )
        return DiagnosisInput(
            transaction_id=recovery.transaction_id,
            amount_cents=ctx.amount_cents,
            currency=ctx.currency,
            gateway_provider=ctx.gateway_provider,
            issuer_id=ctx.issuer_id,
            card_bin=ctx.card_bin,
            decline_code=ctx.decline_code,
            decline_category=cat,
            decline_message=ctx.decline_message,
            gateway_recent_success_rate=ctx.gateway_recent_success_rate,
            issuer_recent_success_rate=ctx.issuer_recent_success_rate,
            similar_failures_last_24h=ctx.similar_failures_last_24h,
            recent_recovery_success_rate=ctx.recent_recovery_success_rate,
        )

    def _build_strategy_input(
        self,
        recovery: Recovery,
        ctx: CoordinatorContext,
        diag: DiagnosisOutput,
        diagnosis_id: DiagnosisId,
    ) -> StrategyInput:
        return StrategyInput(
            transaction_id=recovery.transaction_id,
            diagnosis_id=diagnosis_id,
            amount_cents=ctx.amount_cents,
            currency=ctx.currency,
            gateway_provider=ctx.gateway_provider,
            issuer_id=ctx.issuer_id,
            root_cause_category=diag.root_cause_category,
            is_recoverable=diag.is_recoverable,
            diagnosis_confidence=diag.confidence,
            pattern_delayed_retry_success_rate=ctx.pattern_delayed_retry_success_rate,
            pattern_reroute_success_rate=ctx.pattern_reroute_success_rate,
            pattern_payment_link_success_rate=ctx.pattern_payment_link_success_rate,
            pattern_avg_recovery_delay_seconds=ctx.pattern_avg_recovery_delay_seconds,
            alternate_gateways=list(ctx.alternate_gateways),
            max_delay_seconds=ctx.max_delay_seconds,
        )

    def _build_risk_input(
        self,
        recovery: Recovery,
        ctx: CoordinatorContext,
        strat: StrategyOutput,
        strategy_id: StrategyId,
    ) -> RiskInput:
        return RiskInput(
            transaction_id=recovery.transaction_id,
            strategy_id=strategy_id,
            amount_cents=ctx.amount_cents,
            currency=ctx.currency,
            proposed_strategy=strat.strategy_kind,
            attempt_number=ctx.attempt_number,
            previous_attempts_failed=ctx.previous_attempts_failed,
            gateway_recent_success_rate=ctx.gateway_recent_success_rate,
            issuer_recent_success_rate=ctx.issuer_recent_success_rate,
            historical_dup_charge_rate_for_strategy=ctx.historical_dup_charge_rate_for_strategy,
            strategy_changes_gateway=strat.strategy_kind
            in {RecoveryStrategyKind.GATEWAY_REROUTE, RecoveryStrategyKind.RAIL_SWITCH},
            strategy_delay_seconds=strat.delay_seconds,
        )

    def _build_policy_context(
        self,
        recovery: Recovery,
        ctx: CoordinatorContext,
        strat: StrategyOutput,
        risk: RiskOutput,
    ) -> PolicyContext:
        from reflow.domain.transactions import DeclineCategory

        cat = (
            DeclineCategory(ctx.decline_category_value)
            if ctx.decline_category_value
            else None
        )
        return PolicyContext(
            tenant_id=recovery.tenant_id,
            transaction_id=recovery.transaction_id,
            amount_cents=ctx.amount_cents,
            currency=ctx.currency,
            issuer_id=ctx.issuer_id,
            gateway_id=ctx.gateway_provider,
            attempt_number=ctx.attempt_number,
            decline_category=cat,
            decline_code_normalized=ctx.decline_code,
            proposed_strategy=strat.strategy_kind,
            proposed_delay_seconds=strat.delay_seconds,
            diagnosis_confidence=None,  # populated upstream if needed
            risk_level=risk.overall_risk_level.value,
            duplicate_charge_probability=risk.duplicate_charge_probability,
            expected_recovery_probability=strat.expected_recovery_probability,
            tenant_max_retries=ctx.tenant_max_retries,
            tenant_high_value_threshold_cents=ctx.tenant_high_value_threshold_cents,
            tenant_hitl_required_above_cents=ctx.tenant_hitl_required_above_cents,
            evaluated_at=datetime.now(UTC),
        )

    def _build_guard_input(
        self,
        recovery: Recovery,
        diag: DiagnosisOutput,
        diagnosis_id: DiagnosisId,
        strat: StrategyOutput,
        strategy_id: StrategyId,
        risk: RiskOutput,
        risk_assessment_id: RiskAssessmentId,
        policy_decision_id: PolicyDecisionId,
        policy_outcome: PolicyOutcome,
        policy_matched_rule_id: str | None,
        policy_reason: str,
    ) -> GuardInput:
        return GuardInput(
            transaction_id=recovery.transaction_id,
            diagnosis_id=diagnosis_id,
            strategy_id=strategy_id,
            risk_assessment_id=risk_assessment_id,
            policy_decision_id=policy_decision_id,
            root_cause_category=diag.root_cause_category,
            is_recoverable=diag.is_recoverable,
            diagnosis_confidence=diag.confidence,
            strategy_kind=strat.strategy_kind,
            strategy_expected_recovery_probability=strat.expected_recovery_probability,
            strategy_delay_seconds=strat.delay_seconds,
            strategy_alternate_gateway=strat.alternate_gateway,
            overall_risk_level=risk.overall_risk_level,
            duplicate_charge_probability=risk.duplicate_charge_probability,
            financial_risk_score=risk.financial_risk_score,
            customer_friction_score=risk.customer_friction_score,
            policy_outcome=policy_outcome,
            policy_matched_rule_id=policy_matched_rule_id,
            policy_reason=policy_reason,
        )


def _strategy_params(strat: StrategyOutput) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if strat.delay_seconds is not None:
        out["delay_seconds"] = strat.delay_seconds
    if strat.alternate_gateway is not None:
        out["alternate_gateway"] = strat.alternate_gateway
    return out


def _step(name: str, artifact_id: object | None, telemetry: object) -> StepRecord:
    return StepRecord(
        name=name,
        artifact_id=str(artifact_id) if artifact_id else None,
        telemetry={
            "agent_run_id": str(getattr(telemetry, "agent_run_id", "")),
            "agent_name": getattr(telemetry, "agent_name", None),
            "agent_version": getattr(telemetry, "agent_version", None),
            "prompt_template_name": getattr(telemetry, "prompt_template_name", None),
            "prompt_template_version": getattr(telemetry, "prompt_template_version", None),
            "prompt_template_hash": getattr(telemetry, "prompt_template_hash", None),
            "validation_status": getattr(
                getattr(telemetry, "validation_status", None), "value", None
            ),
            "repair_attempts": getattr(telemetry, "repair_attempts", 0),
            "total_tokens_in": getattr(telemetry, "total_tokens_in", 0),
            "total_tokens_out": getattr(telemetry, "total_tokens_out", 0),
            "total_cost_usd": getattr(telemetry, "total_cost_usd", 0.0),
            "total_latency_ms": getattr(telemetry, "total_latency_ms", 0),
            "provider_chain": getattr(telemetry, "provider_chain", []),
        },
    )
