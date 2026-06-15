"""GuardAgent — final consistency check."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from reflow.agents.diagnosis.schemas import RootCauseCategory
from reflow.agents.guard.agent import GuardAgent
from reflow.agents.guard.schemas import GuardInput
from reflow.agents.llm.client import FinishReason, LLMResponse
from reflow.agents.llm.router import RouteAttempt, RoutedResponse
from reflow.agents.risk.schemas import RiskLevel
from reflow.agents.safety.output_validator import ValidationStatus
from reflow.core.config import LLMProvider
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

pytestmark = pytest.mark.unit


_APPROVE = """
{
  "outcome": "approve",
  "rationale": "All upstream outputs consistent.",
  "concerns": [
    {"severity": "info", "observation": "delay 720s aligns with pattern mean.",
     "source_kind": "consistency_check"}
  ]
}
""".strip()

_BLOCK = """
{
  "outcome": "block",
  "rationale": "duplicate_charge_probability above threshold.",
  "concerns": [
    {"severity": "blocker", "observation": "duplicate_charge_probability >= 0.10",
     "source_kind": "rule_match"}
  ]
}
""".strip()


def _routed(content: str) -> RoutedResponse:
    resp = LLMResponse(
        content=content,
        provider=LLMProvider.GROQ,
        model="m",
        finish_reason=FinishReason.STOP,
        tokens_in=150,
        tokens_out=40,
        cost_usd=0.0001,
        latency_ms=160,
        prompt_hash="h",
    )
    return RoutedResponse(
        response=resp, attempts=[RouteAttempt(provider=LLMProvider.GROQ, model="m", error=None)]
    )


@dataclass
class _MockRouter:
    queue: list[RoutedResponse]
    calls: list[dict] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []
        self._iter: AsyncIterator[RoutedResponse] = self._make_iter()

    async def _make_iter(self) -> AsyncIterator[RoutedResponse]:
        for r in self.queue:
            yield r

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return await self._iter.__anext__()


def _inputs(**overrides) -> GuardInput:
    base: dict = {
        "transaction_id": new_transaction_id(),
        "diagnosis_id": DiagnosisId(new_id()),
        "strategy_id": StrategyId(new_id()),
        "risk_assessment_id": RiskAssessmentId(new_id()),
        "policy_decision_id": PolicyDecisionId(new_id()),
        "root_cause_category": RootCauseCategory.ISSUER_DECLINE,
        "is_recoverable": True,
        "diagnosis_confidence": 0.85,
        "strategy_kind": RecoveryStrategyKind.DELAYED_RETRY,
        "strategy_expected_recovery_probability": 0.65,
        "strategy_delay_seconds": 720,
        "strategy_alternate_gateway": None,
        "overall_risk_level": RiskLevel.LOW,
        "duplicate_charge_probability": 0.02,
        "financial_risk_score": 0.2,
        "customer_friction_score": 0.1,
        "policy_outcome": PolicyOutcome.ALLOW,
        "policy_matched_rule_id": None,
        "policy_reason": "No restrictive rule matched",
    }
    base.update(overrides)
    return GuardInput(**base)


async def test_approve_path() -> None:
    router = _MockRouter(queue=[_routed(_APPROVE)])
    agent = GuardAgent(router=router)  # type: ignore[arg-type]
    result = await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())
    assert result.output.outcome.value == "approve"
    assert result.telemetry.validation_status == ValidationStatus.VALID
    assert result.telemetry.prompt_template_name == "guard.system"


async def test_block_path() -> None:
    router = _MockRouter(queue=[_routed(_BLOCK)])
    agent = GuardAgent(router=router)  # type: ignore[arg-type]
    result = await agent.run(tenant_id=new_tenant_id(), inputs=_inputs(duplicate_charge_probability=0.25))
    assert result.output.outcome.value == "block"
    assert any(c.severity == "blocker" for c in result.output.concerns)


async def test_user_prompt_includes_all_chain_data() -> None:
    router = _MockRouter(queue=[_routed(_APPROVE)])
    agent = GuardAgent(router=router)  # type: ignore[arg-type]
    await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())
    sent = router.calls[0]["user_prompt"]
    assert '"diagnosis":' in sent
    assert '"strategy":' in sent
    assert '"risk":' in sent
    assert '"policy":' in sent
