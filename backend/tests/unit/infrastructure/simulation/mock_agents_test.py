"""Mock agents — deterministic outputs, schema conformance, drop-in protocol."""

from __future__ import annotations

import pytest

from reflow.agents.diagnosis.schemas import DiagnosisInput, RootCauseCategory
from reflow.agents.guard.schemas import GuardInput, GuardOutcome
from reflow.agents.risk.schemas import RiskInput, RiskLevel
from reflow.agents.strategy.schemas import StrategyInput
from reflow.core.types import (
    DiagnosisId,
    PolicyDecisionId,
    RiskAssessmentId,
    StrategyId,
    new_id,
    new_tenant_id,
    new_transaction_id,
)
from reflow.domain.policy import PolicyOutcome, RecoveryStrategyKind
from reflow.domain.transactions import DeclineCategory
from reflow.infrastructure.simulation.mock_agents import (
    MockDiagnosisAgent,
    MockGuardAgent,
    MockRiskAgent,
    MockStrategyAgent,
    build_mock_coordinator,
)

pytestmark = pytest.mark.unit


def _diag_input(category: DeclineCategory = DeclineCategory.ISSUER) -> DiagnosisInput:
    return DiagnosisInput(
        transaction_id=new_transaction_id(),
        amount_cents=4999,
        currency="USD",
        gateway_provider="stripe",
        decline_category=category,
        decline_code="ISSUER_DO_NOT_HONOR",
        issuer_recent_success_rate=0.63,
    )


def _strat_input(
    category: RootCauseCategory = RootCauseCategory.ISSUER_DECLINE,
) -> StrategyInput:
    return StrategyInput(
        transaction_id=new_transaction_id(),
        diagnosis_id=DiagnosisId(new_id()),
        amount_cents=4999,
        currency="USD",
        gateway_provider="stripe",
        root_cause_category=category,
        is_recoverable=True,
        diagnosis_confidence=0.85,
        pattern_avg_recovery_delay_seconds=720,
        alternate_gateways=["adyen"],
    )


def _risk_input(
    *, attempt_number: int = 1, changes_gateway: bool = False
) -> RiskInput:
    return RiskInput(
        transaction_id=new_transaction_id(),
        strategy_id=StrategyId(new_id()),
        amount_cents=4999,
        currency="USD",
        proposed_strategy=RecoveryStrategyKind.DELAYED_RETRY,
        attempt_number=attempt_number,
        previous_attempts_failed=attempt_number - 1,
        strategy_changes_gateway=changes_gateway,
        strategy_delay_seconds=720,
    )


def _guard_input(*, policy: PolicyOutcome, dup_p: float = 0.02) -> GuardInput:
    return GuardInput(
        transaction_id=new_transaction_id(),
        diagnosis_id=DiagnosisId(new_id()),
        strategy_id=StrategyId(new_id()),
        risk_assessment_id=RiskAssessmentId(new_id()),
        policy_decision_id=PolicyDecisionId(new_id()),
        root_cause_category=RootCauseCategory.ISSUER_DECLINE,
        is_recoverable=True,
        diagnosis_confidence=0.85,
        strategy_kind=RecoveryStrategyKind.DELAYED_RETRY,
        strategy_expected_recovery_probability=0.65,
        overall_risk_level=RiskLevel.LOW,
        duplicate_charge_probability=dup_p,
        financial_risk_score=0.2,
        customer_friction_score=0.1,
        policy_outcome=policy,
        policy_reason="test",
    )


class TestDeterminism:
    async def test_diagnosis_same_input_same_output(self) -> None:
        inp = _diag_input()
        a = await MockDiagnosisAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        b = await MockDiagnosisAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        # Run IDs differ; outputs match.
        assert a.output == b.output

    async def test_strategy_same_input_same_output(self) -> None:
        inp = _strat_input()
        a = await MockStrategyAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        b = await MockStrategyAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        assert a.output == b.output

    async def test_risk_same_input_same_output(self) -> None:
        inp = _risk_input()
        a = await MockRiskAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        b = await MockRiskAgent().run(tenant_id=new_tenant_id(), inputs=inp)
        assert a.output == b.output


class TestMappings:
    async def test_diagnosis_maps_category_to_root_cause(self) -> None:
        for cat, expected in [
            (DeclineCategory.ISSUER, RootCauseCategory.ISSUER_DECLINE),
            (DeclineCategory.FRAUD,  RootCauseCategory.FRAUD_SIGNAL),
            (DeclineCategory.FUNDS,  RootCauseCategory.INSUFFICIENT_FUNDS),
        ]:
            r = await MockDiagnosisAgent().run(
                tenant_id=new_tenant_id(), inputs=_diag_input(cat)
            )
            assert r.output.root_cause_category == expected

    async def test_diagnosis_fraud_is_not_recoverable(self) -> None:
        r = await MockDiagnosisAgent().run(
            tenant_id=new_tenant_id(), inputs=_diag_input(DeclineCategory.FRAUD)
        )
        assert r.output.is_recoverable is False

    async def test_strategy_picks_reroute_for_gateway_degraded(self) -> None:
        r = await MockStrategyAgent().run(
            tenant_id=new_tenant_id(),
            inputs=_strat_input(RootCauseCategory.GATEWAY_DEGRADED),
        )
        assert r.output.strategy_kind == RecoveryStrategyKind.GATEWAY_REROUTE
        assert r.output.alternate_gateway is not None

    async def test_strategy_picks_payment_link_for_funds(self) -> None:
        r = await MockStrategyAgent().run(
            tenant_id=new_tenant_id(),
            inputs=_strat_input(RootCauseCategory.INSUFFICIENT_FUNDS),
        )
        assert r.output.strategy_kind == RecoveryStrategyKind.PAYMENT_LINK_NUDGE

    async def test_risk_duplicate_probability_grows_with_attempts(self) -> None:
        early = await MockRiskAgent().run(
            tenant_id=new_tenant_id(), inputs=_risk_input(attempt_number=1)
        )
        late = await MockRiskAgent().run(
            tenant_id=new_tenant_id(), inputs=_risk_input(attempt_number=5)
        )
        assert late.output.duplicate_charge_probability >= early.output.duplicate_charge_probability

    async def test_guard_blocks_on_policy_deny(self) -> None:
        r = await MockGuardAgent().run(
            tenant_id=new_tenant_id(),
            inputs=_guard_input(policy=PolicyOutcome.DENY),
        )
        assert r.output.outcome == GuardOutcome.BLOCK
        assert any(c.severity == "blocker" for c in r.output.concerns)

    async def test_guard_blocks_on_high_dup_charge(self) -> None:
        r = await MockGuardAgent().run(
            tenant_id=new_tenant_id(),
            inputs=_guard_input(policy=PolicyOutcome.ALLOW, dup_p=0.20),
        )
        assert r.output.outcome == GuardOutcome.BLOCK

    async def test_guard_approves_on_clean_chain(self) -> None:
        r = await MockGuardAgent().run(
            tenant_id=new_tenant_id(),
            inputs=_guard_input(policy=PolicyOutcome.ALLOW, dup_p=0.02),
        )
        assert r.output.outcome == GuardOutcome.APPROVE


class TestCoordinatorFactory:
    def test_build_mock_coordinator_returns_real_coordinator(self) -> None:
        c = build_mock_coordinator()
        # Has all 4 agent attributes.
        assert hasattr(c, "_diagnosis")
        assert hasattr(c, "_strategy")
        assert hasattr(c, "_risk")
        assert hasattr(c, "_guard")
