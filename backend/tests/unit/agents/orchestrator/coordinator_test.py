"""RecoveryCoordinator — chain orchestration tests with mocked agents.

These verify:
    * Happy path walks Diagnosis -> Strategy -> Risk -> Policy -> Guard
      and lands in policy_evaluated state (ready_to_execute)
    * Not-recoverable diagnosis aborts via abandon()
    * Agent failure aborts with stopped_reason and fail()
    * Policy DENY halts at policy_evaluated with stopped_reason=policy_denied
    * Guard BLOCK fails the recovery with stopped_reason=guard_blocked
    * Step records carry telemetry from every agent
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reflow.agents.diagnosis.schemas import (
    DiagnosisOutput,
    EvidenceItem,
    RootCauseCategory,
)
from reflow.agents.guard.schemas import GuardConcern, GuardOutcome, GuardOutput
from reflow.agents.orchestrator.coordinator import (
    CoordinatorContext,
    RecoveryCoordinator,
)
from reflow.agents.risk.schemas import RiskFactor, RiskLevel, RiskOutput
from reflow.agents.strategy.schemas import StrategyEvidenceItem, StrategyOutput
from reflow.core.types import AgentRunId, new_id, new_tenant_id, new_transaction_id
from reflow.domain.policy import RecoveryStrategyKind
from reflow.domain.recovery import Recovery, RecoveryState

pytestmark = pytest.mark.unit


# -----------------------------------------------------------------------------
# Fake agents that return canned outputs.
# -----------------------------------------------------------------------------


@dataclass
class _FakeAgentResult:
    output: object
    telemetry: object


@dataclass
class _FakeTelemetry:
    agent_run_id: AgentRunId
    agent_name: str
    agent_version: str = "1.0.0"
    prompt_template_name: str = "test"
    prompt_template_version: int = 1
    prompt_template_hash: str = "h"
    validation_status = type("S", (), {"value": "valid"})()  # type: ignore[assignment]
    repair_attempts: int = 0
    total_tokens_in: int = 100
    total_tokens_out: int = 50
    total_cost_usd: float = 0.0001
    total_latency_ms: int = 100
    provider_chain: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.provider_chain is None:
            self.provider_chain = ["groq"]


class _FakeAgent:
    def __init__(self, name: str, output: object, *, raise_exc: Exception | None = None) -> None:
        self._name = name
        self._output = output
        self._raise = raise_exc

    async def run(self, *, tenant_id, inputs):  # type: ignore[override]
        if self._raise:
            raise self._raise
        return _FakeAgentResult(
            output=self._output,
            telemetry=_FakeTelemetry(
                agent_run_id=AgentRunId(new_id()), agent_name=self._name
            ),
        )


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


def _diag_output(
    *, recoverable: bool = True, confidence: float = 0.85
) -> DiagnosisOutput:
    return DiagnosisOutput(
        root_cause="Issuer slowdown",
        root_cause_category=RootCauseCategory.ISSUER_DECLINE,
        is_recoverable=recoverable,
        confidence=confidence,
        reasoning="ok",
        evidence=[
            EvidenceItem(
                observation="x", source_kind="issuer_health", weight=0.5
            )
        ],
    )


def _strat_output(
    *, kind: RecoveryStrategyKind = RecoveryStrategyKind.DELAYED_RETRY
) -> StrategyOutput:
    return StrategyOutput(
        strategy_kind=kind,
        delay_seconds=720 if kind == RecoveryStrategyKind.DELAYED_RETRY else None,
        alternate_gateway=None
        if kind != RecoveryStrategyKind.GATEWAY_REROUTE
        else "adyen",
        expected_recovery_probability=0.6,
        expected_latency_seconds=720,
        rationale="ok",
        evidence=[
            StrategyEvidenceItem(
                observation="x", source_kind="pattern_match", weight=0.5
            )
        ],
    )


def _risk_output(*, dup_p: float = 0.02) -> RiskOutput:
    return RiskOutput(
        financial_risk_score=0.2,
        operational_risk_score=0.2,
        customer_friction_score=0.1,
        duplicate_charge_probability=dup_p,
        overall_risk_level=RiskLevel.LOW,
        rationale="ok",
        factors=[
            RiskFactor(
                dimension="duplicate_charge",
                observation="x",
                contribution=0.1,
                source_kind="rule_match",
            )
        ],
    )


def _guard_output(outcome: GuardOutcome = GuardOutcome.APPROVE) -> GuardOutput:
    concerns = []
    if outcome == GuardOutcome.BLOCK:
        concerns = [
            GuardConcern(severity="blocker", observation="x", source_kind="rule_match")
        ]
    elif outcome == GuardOutcome.HOLD:
        concerns = [
            GuardConcern(severity="warning", observation="x", source_kind="rule_match")
        ]
    return GuardOutput(outcome=outcome, rationale="ok", concerns=concerns)


def _coord(
    *,
    diag_output: DiagnosisOutput | None = None,
    diag_exc: Exception | None = None,
    strat_output: StrategyOutput | None = None,
    risk_output: RiskOutput | None = None,
    guard_output: GuardOutput | None = None,
) -> RecoveryCoordinator:
    return RecoveryCoordinator(
        diagnosis=_FakeAgent("diagnosis", diag_output or _diag_output(), raise_exc=diag_exc),
        strategy=_FakeAgent("strategy", strat_output or _strat_output()),
        risk=_FakeAgent("risk", risk_output or _risk_output()),
        guard=_FakeAgent("guard", guard_output or _guard_output()),
    )


def _recovery() -> Recovery:
    return Recovery.start(
        recovery_id=Recovery.new_id(),
        tenant_id=new_tenant_id(),
        transaction_id=new_transaction_id(),
        attempt_number=1,
    )


def _ctx() -> CoordinatorContext:
    return CoordinatorContext(
        amount_cents=4999,
        currency="USD",
        gateway_provider="stripe",
        issuer_id="ISSUER_X",
        card_bin="424242",
        decline_code="insufficient_funds",
        decline_category_value="funds",
        decline_message="declined",
        gateway_recent_success_rate=0.92,
        issuer_recent_success_rate=0.63,
        similar_failures_last_24h=413,
        recent_recovery_success_rate=0.42,
        pattern_delayed_retry_success_rate=0.65,
        pattern_avg_recovery_delay_seconds=720,
        alternate_gateways=("adyen",),
        attempt_number=1,
        previous_attempts_failed=0,
    )


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


async def test_happy_path_reaches_ready_to_execute() -> None:
    rec = _recovery()
    result = await _coord().run_full(recovery=rec, ctx=_ctx())

    assert result.stopped_reason == "ready_to_execute"
    assert [s.name for s in result.steps] == [
        "diagnosis",
        "strategy",
        "risk",
        "policy",
        "guard",
    ]
    # Reached policy_evaluated (no execution step yet by design).
    assert rec.state == RecoveryState.POLICY_EVALUATED


async def test_not_recoverable_aborts_and_abandons() -> None:
    rec = _recovery()
    result = await _coord(
        diag_output=_diag_output(recoverable=False)
    ).run_full(recovery=rec, ctx=_ctx())

    assert result.stopped_reason == "not_recoverable"
    assert rec.state == RecoveryState.ABANDONED
    # Only diagnosis ran.
    assert [s.name for s in result.steps] == ["diagnosis"]


async def test_diagnosis_failure_fails_recovery() -> None:
    rec = _recovery()
    result = await _coord(diag_exc=RuntimeError("LLM exploded")).run_full(
        recovery=rec, ctx=_ctx()
    )
    assert result.stopped_reason == "diagnosis_failed"
    assert rec.state == RecoveryState.FAILED


async def test_policy_deny_halts_at_policy_evaluated() -> None:
    # Force policy DENY via dup_p above threshold (0.10).
    rec = _recovery()
    result = await _coord(risk_output=_risk_output(dup_p=0.25)).run_full(
        recovery=rec, ctx=_ctx()
    )
    assert result.stopped_reason == "policy_denied"
    # PolicyEvaluated -> RecoveryFailed (deny emits both).
    assert rec.state == RecoveryState.FAILED
    # Guard never ran.
    names = [s.name for s in result.steps]
    assert "policy" in names
    assert "guard" not in names


async def test_guard_block_fails_recovery() -> None:
    rec = _recovery()
    result = await _coord(
        guard_output=_guard_output(GuardOutcome.BLOCK)
    ).run_full(recovery=rec, ctx=_ctx())
    assert result.stopped_reason == "guard_blocked"
    assert rec.state == RecoveryState.FAILED


async def test_guard_hold_stops_without_failing() -> None:
    rec = _recovery()
    result = await _coord(
        guard_output=_guard_output(GuardOutcome.HOLD)
    ).run_full(recovery=rec, ctx=_ctx())
    assert result.stopped_reason == "guard_hold"
    # State should NOT be FAILED; it stays at policy_evaluated.
    assert rec.state == RecoveryState.POLICY_EVALUATED


async def test_steps_carry_telemetry() -> None:
    rec = _recovery()
    result = await _coord().run_full(recovery=rec, ctx=_ctx())
    diag_step = next(s for s in result.steps if s.name == "diagnosis")
    assert diag_step.telemetry["agent_name"] == "diagnosis"
    assert diag_step.telemetry["validation_status"] == "valid"
    assert diag_step.telemetry["total_tokens_in"] == 100
    assert diag_step.artifact_id is not None  # diagnosis_id

    policy_step = next(s for s in result.steps if s.name == "policy")
    assert policy_step.artifact_id is not None
    assert policy_step.telemetry["outcome"] == "allow"
