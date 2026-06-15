"""RiskAgent — multi-dimensional scoring + duplicate_charge_probability."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from reflow.agents.llm.client import FinishReason, LLMResponse
from reflow.agents.llm.router import RouteAttempt, RoutedResponse
from reflow.agents.risk.agent import RiskAgent
from reflow.agents.risk.schemas import RiskInput
from reflow.agents.safety.output_validator import ValidationStatus
from reflow.core.config import LLMProvider
from reflow.core.exceptions import LLMValidationError
from reflow.core.types import StrategyId, new_id, new_tenant_id, new_transaction_id
from reflow.domain.policy import RecoveryStrategyKind

pytestmark = pytest.mark.unit


_VALID = """
{
  "financial_risk_score": 0.20,
  "operational_risk_score": 0.30,
  "customer_friction_score": 0.10,
  "duplicate_charge_probability": 0.02,
  "overall_risk_level": "low",
  "expected_revenue_impact_cents": 4500,
  "rationale": "Low duplicate risk; delayed retry on same gateway is safe.",
  "factors": [
    {"dimension": "duplicate_charge", "observation": "Same gateway, no reroute.",
     "contribution": 0.1, "source_kind": "rule_match"}
  ]
}
""".strip()

_OUT_OF_RANGE = """
{"financial_risk_score": 1.5, "operational_risk_score": 0.3, "customer_friction_score": 0.1,
 "duplicate_charge_probability": 0.02, "overall_risk_level": "low", "rationale": "x",
 "factors": [{"dimension": "duplicate_charge", "observation": "y", "contribution": 0.1, "source_kind": "z"}]}
""".strip()


def _routed(content: str) -> RoutedResponse:
    resp = LLMResponse(
        content=content,
        provider=LLMProvider.GROQ,
        model="m",
        finish_reason=FinishReason.STOP,
        tokens_in=150,
        tokens_out=60,
        cost_usd=0.00015,
        latency_ms=200,
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


def _inputs(**overrides) -> RiskInput:
    base: dict = {
        "transaction_id": new_transaction_id(),
        "strategy_id": StrategyId(new_id()),
        "amount_cents": 4999,
        "currency": "USD",
        "proposed_strategy": RecoveryStrategyKind.DELAYED_RETRY,
        "attempt_number": 2,
        "previous_attempts_failed": 1,
        "gateway_recent_success_rate": 0.92,
        "strategy_changes_gateway": False,
        "strategy_delay_seconds": 720,
    }
    base.update(overrides)
    return RiskInput(**base)


async def test_valid_risk_response() -> None:
    router = _MockRouter(queue=[_routed(_VALID)])
    agent = RiskAgent(router=router)  # type: ignore[arg-type]
    result = await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())

    assert 0.0 <= result.output.duplicate_charge_probability <= 1.0
    assert result.output.overall_risk_level.value == "low"
    assert len(result.output.factors) == 1
    assert result.telemetry.validation_status == ValidationStatus.VALID
    assert result.telemetry.prompt_template_name == "risk.system"


async def test_out_of_range_score_repaired_then_fails() -> None:
    router = _MockRouter(queue=[_routed(_OUT_OF_RANGE)] * 3)
    agent = RiskAgent(router=router)  # type: ignore[arg-type]
    with pytest.raises(LLMValidationError):
        await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())
