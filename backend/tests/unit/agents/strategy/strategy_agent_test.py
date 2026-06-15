"""StrategyAgent — schema enforcement + telemetry."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest

from reflow.agents.diagnosis.schemas import RootCauseCategory
from reflow.agents.llm.client import FinishReason, LLMResponse
from reflow.agents.llm.router import RouteAttempt, RoutedResponse
from reflow.agents.safety.output_validator import ValidationStatus
from reflow.agents.strategy.agent import StrategyAgent
from reflow.agents.strategy.schemas import StrategyInput
from reflow.core.config import LLMProvider
from reflow.core.exceptions import LLMValidationError
from reflow.core.types import DiagnosisId, new_id, new_tenant_id, new_transaction_id

pytestmark = pytest.mark.unit


_VALID = """
{
  "strategy_kind": "delayed_retry",
  "delay_seconds": 720,
  "alternate_gateway": null,
  "expected_recovery_probability": 0.65,
  "expected_latency_seconds": 720,
  "rationale": "Pattern memory shows 65% recovery after a 12-minute cooldown.",
  "evidence": [
    {"observation": "pattern_delayed_retry_success_rate = 0.65", "source_kind": "pattern_match", "weight": 0.8},
    {"observation": "pattern_avg_recovery_delay_seconds = 720", "source_kind": "pattern_match", "weight": 0.6}
  ]
}
""".strip()

_NO_EVIDENCE = """
{"strategy_kind": "graceful_failure", "delay_seconds": null, "alternate_gateway": null,
 "expected_recovery_probability": 0.0, "expected_latency_seconds": 0,
 "rationale": "x", "evidence": []}
""".strip()


def _routed(content: str) -> RoutedResponse:
    resp = LLMResponse(
        content=content,
        provider=LLMProvider.GROQ,
        model="test-model",
        finish_reason=FinishReason.STOP,
        tokens_in=200,
        tokens_out=80,
        cost_usd=0.0002,
        latency_ms=240,
        prompt_hash="h",
    )
    return RoutedResponse(
        response=resp, attempts=[RouteAttempt(provider=LLMProvider.GROQ, model="test-model", error=None)]
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


def _inputs(**overrides) -> StrategyInput:
    base: dict = {
        "transaction_id": new_transaction_id(),
        "diagnosis_id": DiagnosisId(new_id()),
        "amount_cents": 5000,
        "currency": "USD",
        "gateway_provider": "stripe",
        "issuer_id": "ISSUER_X",
        "root_cause_category": RootCauseCategory.ISSUER_DECLINE,
        "is_recoverable": True,
        "diagnosis_confidence": 0.85,
        "pattern_delayed_retry_success_rate": 0.65,
        "pattern_avg_recovery_delay_seconds": 720,
        "alternate_gateways": ["adyen"],
        "max_delay_seconds": 86_400,
    }
    base.update(overrides)
    return StrategyInput(**base)


async def test_valid_strategy_response() -> None:
    router = _MockRouter(queue=[_routed(_VALID)])
    agent = StrategyAgent(router=router)  # type: ignore[arg-type]
    result = await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())

    assert result.output.strategy_kind.value == "delayed_retry"
    assert result.output.delay_seconds == 720
    assert len(result.output.evidence) == 2
    assert result.telemetry.validation_status == ValidationStatus.VALID
    assert result.telemetry.prompt_template_name == "strategy.system"


async def test_missing_evidence_fails_after_repair() -> None:
    router = _MockRouter(queue=[_routed(_NO_EVIDENCE)] * 3)
    agent = StrategyAgent(router=router)  # type: ignore[arg-type]
    with pytest.raises(LLMValidationError):
        await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())


async def test_user_prompt_is_json() -> None:
    router = _MockRouter(queue=[_routed(_VALID)])
    agent = StrategyAgent(router=router)  # type: ignore[arg-type]
    await agent.run(tenant_id=new_tenant_id(), inputs=_inputs())
    sent = router.calls[0]["user_prompt"]
    assert '"diagnosis":' in sent
    assert '"pattern_memory":' in sent
    assert '"constraints":' in sent
