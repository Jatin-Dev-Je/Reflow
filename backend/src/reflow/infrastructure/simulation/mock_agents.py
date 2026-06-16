"""Mock agent set for deterministic simulation runs.

The real agents call an LLM. In demos / CI / load tests we don't want to
burn provider credits or depend on free-tier rate limits. These mocks produce
plausible, deterministic outputs derived from the input — same input always
gives same output, but the outputs reflect realistic patterns.

The mock agents implement the same async `run(tenant_id, inputs)` protocol
the coordinator expects, so they're drop-in replacements.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from reflow.agents.base.agent import AgentTelemetry
from reflow.agents.diagnosis.schemas import (
    DiagnosisInput,
    DiagnosisOutput,
    EvidenceItem,
    RootCauseCategory,
)
from reflow.agents.guard.schemas import (
    GuardConcern,
    GuardInput,
    GuardOutcome,
    GuardOutput,
)
from reflow.agents.risk.schemas import (
    RiskFactor,
    RiskInput,
    RiskLevel,
    RiskOutput,
)
from reflow.agents.safety.output_validator import ValidationStatus
from reflow.agents.strategy.schemas import (
    StrategyEvidenceItem,
    StrategyInput,
    StrategyOutput,
)
from reflow.core.types import AgentRunId, TenantId, new_id
from reflow.domain.policy import RecoveryStrategyKind
from reflow.domain.transactions import DeclineCategory


@dataclass
class _MockResult:
    output: object
    telemetry: AgentTelemetry


def _det_float(seed: str, lo: float, hi: float) -> float:
    h = hashlib.sha256(seed.encode()).digest()
    n = int.from_bytes(h[:8], "big") / 2**64
    return lo + n * (hi - lo)


def _det_int(seed: str, lo: int, hi: int) -> int:
    return int(_det_float(seed, lo, hi))


def _telemetry(agent_name: str, prompt_name: str) -> AgentTelemetry:
    return AgentTelemetry(
        agent_run_id=AgentRunId(new_id()),
        agent_name=agent_name,
        agent_version="mock-1.0",
        prompt_template_name=prompt_name,
        prompt_template_version=0,  # 0 marks 'mock — not a real prompt'
        prompt_template_hash="0" * 64,
        validation_status=ValidationStatus.VALID,
        repair_attempts=0,
        total_tokens_in=0,
        total_tokens_out=0,
        total_cost_usd=0.0,
        total_latency_ms=10,
        provider_chain=["mock"],
        succeeded=True,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


# -----------------------------------------------------------------------------
# Diagnosis
# -----------------------------------------------------------------------------


_DECLINE_TO_ROOT: dict[DeclineCategory | None, RootCauseCategory] = {
    DeclineCategory.ISSUER:         RootCauseCategory.ISSUER_DECLINE,
    DeclineCategory.NETWORK:        RootCauseCategory.NETWORK,
    DeclineCategory.FRAUD:          RootCauseCategory.FRAUD_SIGNAL,
    DeclineCategory.AUTHENTICATION: RootCauseCategory.AUTHENTICATION,
    DeclineCategory.FUNDS:          RootCauseCategory.INSUFFICIENT_FUNDS,
    DeclineCategory.GATEWAY:        RootCauseCategory.GATEWAY_DEGRADED,
    DeclineCategory.OTHER:          RootCauseCategory.OTHER,
    None:                           RootCauseCategory.OTHER,
}

# Hard-decline categories produce is_recoverable=False.
_HARD_CATEGORIES: set[RootCauseCategory] = {
    RootCauseCategory.FRAUD_SIGNAL,
}


class MockDiagnosisAgent:
    async def run(
        self, *, tenant_id: TenantId, inputs: DiagnosisInput  # noqa: ARG002
    ) -> _MockResult:
        cat = _DECLINE_TO_ROOT.get(inputs.decline_category, RootCauseCategory.OTHER)
        seed = f"diag:{inputs.transaction_id}"
        confidence = _det_float(seed, 0.60, 0.95)
        is_recoverable = cat not in _HARD_CATEGORIES

        evidence = [
            EvidenceItem(
                observation=(
                    f"Decline code {inputs.decline_code or 'UNKNOWN'} "
                    f"in category {cat.value}"
                ),
                source_kind="rule_match",
                weight=0.6,
            )
        ]
        if inputs.issuer_recent_success_rate is not None:
            evidence.append(
                EvidenceItem(
                    observation=(
                        f"issuer_recent_success_rate = "
                        f"{inputs.issuer_recent_success_rate:.2f}"
                    ),
                    source_kind="issuer_health",
                    weight=0.4,
                )
            )

        out = DiagnosisOutput(
            root_cause=f"Mock diagnosis: {cat.value}",
            root_cause_category=cat,
            is_recoverable=is_recoverable,
            confidence=confidence,
            reasoning=(
                f"Mock reasoning based on decline category {cat.value}."
            ),
            evidence=evidence,
        )
        return _MockResult(output=out, telemetry=_telemetry("diagnosis", "mock.diagnosis"))


# -----------------------------------------------------------------------------
# Strategy
# -----------------------------------------------------------------------------


_CATEGORY_TO_STRATEGY: dict[RootCauseCategory, RecoveryStrategyKind] = {
    RootCauseCategory.ISSUER_DECLINE:     RecoveryStrategyKind.DELAYED_RETRY,
    RootCauseCategory.ISSUER_OUTAGE:      RecoveryStrategyKind.DELAYED_RETRY,
    RootCauseCategory.GATEWAY_DEGRADED:   RecoveryStrategyKind.GATEWAY_REROUTE,
    RootCauseCategory.GATEWAY_OUTAGE:     RecoveryStrategyKind.GATEWAY_REROUTE,
    RootCauseCategory.NETWORK:            RecoveryStrategyKind.DELAYED_RETRY,
    RootCauseCategory.AUTHENTICATION:     RecoveryStrategyKind.PAYMENT_LINK_NUDGE,
    RootCauseCategory.INSUFFICIENT_FUNDS: RecoveryStrategyKind.PAYMENT_LINK_NUDGE,
    RootCauseCategory.FRAUD_SIGNAL:       RecoveryStrategyKind.GRACEFUL_FAILURE,
    RootCauseCategory.OTHER:              RecoveryStrategyKind.DELAYED_RETRY,
}


class MockStrategyAgent:
    async def run(
        self, *, tenant_id: TenantId, inputs: StrategyInput  # noqa: ARG002
    ) -> _MockResult:
        kind = _CATEGORY_TO_STRATEGY.get(
            inputs.root_cause_category, RecoveryStrategyKind.DELAYED_RETRY
        )

        delay_seconds: int | None = None
        alternate_gateway: str | None = None
        if kind == RecoveryStrategyKind.DELAYED_RETRY:
            delay_seconds = inputs.pattern_avg_recovery_delay_seconds or 720
        if kind in {
            RecoveryStrategyKind.GATEWAY_REROUTE,
            RecoveryStrategyKind.RAIL_SWITCH,
        }:
            alternate_gateway = (
                inputs.alternate_gateways[0] if inputs.alternate_gateways else "adyen"
            )

        seed = f"strat:{inputs.transaction_id}:{kind.value}"
        prob = _det_float(seed, 0.45, 0.80)

        out = StrategyOutput(
            strategy_kind=kind,
            delay_seconds=delay_seconds,
            alternate_gateway=alternate_gateway,
            expected_recovery_probability=prob,
            expected_latency_seconds=delay_seconds or 120,
            rationale=(
                f"Mock strategy: {kind.value} for "
                f"{inputs.root_cause_category.value}."
            ),
            evidence=[
                StrategyEvidenceItem(
                    observation=(
                        f"Pattern memory recovery rate for {kind.value} = {prob:.2f}"
                    ),
                    source_kind="pattern_match",
                    weight=0.7,
                )
            ],
        )
        return _MockResult(output=out, telemetry=_telemetry("strategy", "mock.strategy"))


# -----------------------------------------------------------------------------
# Risk
# -----------------------------------------------------------------------------


class MockRiskAgent:
    async def run(
        self, *, tenant_id: TenantId, inputs: RiskInput  # noqa: ARG002
    ) -> _MockResult:
        seed = f"risk:{inputs.transaction_id}:{inputs.proposed_strategy.value}"
        financial = _det_float(seed + "f", 0.05, 0.45)
        operational = _det_float(seed + "o", 0.05, 0.40)
        friction = _det_float(seed + "fr", 0.02, 0.30)

        # duplicate probability grows with attempt count, gateway changes.
        base_dup = 0.01 + 0.02 * max(0, inputs.attempt_number - 1)
        if inputs.strategy_changes_gateway:
            base_dup += 0.03
        dup_p = min(base_dup, 0.20)

        max_score = max(financial, operational, friction, dup_p)
        if max_score >= 0.75:
            level = RiskLevel.CRITICAL
        elif max_score >= 0.50:
            level = RiskLevel.HIGH
        elif max_score >= 0.25:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        out = RiskOutput(
            financial_risk_score=financial,
            operational_risk_score=operational,
            customer_friction_score=friction,
            duplicate_charge_probability=dup_p,
            overall_risk_level=level,
            expected_revenue_impact_cents=inputs.amount_cents // 2,
            rationale="Mock risk: deterministic scoring from input signals.",
            factors=[
                RiskFactor(
                    dimension="duplicate_charge",
                    observation=(
                        f"attempt #{inputs.attempt_number}, "
                        f"changes_gateway={inputs.strategy_changes_gateway}"
                    ),
                    contribution=dup_p,
                    source_kind="rule_match",
                )
            ],
        )
        return _MockResult(output=out, telemetry=_telemetry("risk", "mock.risk"))


# -----------------------------------------------------------------------------
# Guard
# -----------------------------------------------------------------------------


class MockGuardAgent:
    async def run(
        self, *, tenant_id: TenantId, inputs: GuardInput  # noqa: ARG002
    ) -> _MockResult:
        # Mirrors the prompt rules to keep tests / simulations consistent.
        if inputs.policy_outcome.value == "deny":
            outcome = GuardOutcome.BLOCK
            concerns = [
                GuardConcern(
                    severity="blocker",
                    observation="policy denied",
                    source_kind="rule_match",
                )
            ]
        elif inputs.duplicate_charge_probability >= 0.10:
            outcome = GuardOutcome.BLOCK
            concerns = [
                GuardConcern(
                    severity="blocker",
                    observation=(
                        f"duplicate_charge_probability "
                        f"{inputs.duplicate_charge_probability:.2f} >= 0.10"
                    ),
                    source_kind="rule_match",
                )
            ]
        elif inputs.overall_risk_level.value == "critical":
            outcome = GuardOutcome.BLOCK
            concerns = [
                GuardConcern(
                    severity="blocker",
                    observation="overall_risk_level=critical",
                    source_kind="rule_match",
                )
            ]
        elif inputs.diagnosis_confidence < 0.4:
            outcome = GuardOutcome.HOLD
            concerns = [
                GuardConcern(
                    severity="warning",
                    observation=(
                        f"diagnosis_confidence "
                        f"{inputs.diagnosis_confidence:.2f} < 0.4"
                    ),
                    source_kind="rule_match",
                )
            ]
        else:
            outcome = GuardOutcome.APPROVE
            concerns = []

        out = GuardOutput(
            outcome=outcome,
            rationale="Mock guard: applied consistency-check rules.",
            concerns=concerns,
        )
        return _MockResult(output=out, telemetry=_telemetry("guard", "mock.guard"))


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------


from reflow.agents.orchestrator.coordinator import RecoveryCoordinator  # noqa: E402


def build_mock_coordinator() -> RecoveryCoordinator:
    return RecoveryCoordinator(
        diagnosis=MockDiagnosisAgent(),  # type: ignore[arg-type]
        strategy=MockStrategyAgent(),    # type: ignore[arg-type]
        risk=MockRiskAgent(),            # type: ignore[arg-type]
        guard=MockGuardAgent(),          # type: ignore[arg-type]
    )
