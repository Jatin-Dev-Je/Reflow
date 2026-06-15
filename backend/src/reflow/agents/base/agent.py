"""Base Agent class.

An Agent is a deterministic pipeline:
    1. Build a user prompt from typed inputs (sanitized).
    2. Call the LLM router with a versioned system prompt.
    3. Validate the output against a Pydantic schema (repair if needed).
    4. Emit telemetry (provider, tokens, cost, latency, attempts).
    5. Return a typed result.

Subclasses implement `build_user_prompt`, `system_prompt`, and `OutputSchema`.
Everything else — routing, validation, telemetry — is inherited.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

from reflow.agents.base.prompt import PromptTemplate
from reflow.agents.llm.router import LLMRouter, RoutedResponse
from reflow.agents.safety.output_validator import (
    ValidatedOutput,
    ValidationStatus,
    validate_or_repair,
)
from reflow.core.observability.logging import get_logger
from reflow.core.types import AgentRunId, TenantId, new_id

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentTelemetry:
    """Per-run telemetry the caller persists to obs.agent_runs."""

    agent_run_id: AgentRunId
    agent_name: str
    agent_version: str
    prompt_template_name: str
    prompt_template_version: int
    prompt_template_hash: str

    validation_status: ValidationStatus
    repair_attempts: int

    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    total_latency_ms: int

    provider_chain: list[str]  # ['groq', 'gemini'] if fallback fired
    succeeded: bool
    error: str | None = None

    started_at: datetime = datetime.now(UTC)
    completed_at: datetime | None = None


TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class AgentResult(Generic[TOutput]):
    """Typed result + telemetry."""

    output: TOutput
    telemetry: AgentTelemetry


class BaseAgent(Generic[TInput, TOutput]):
    """Abstract base for every agent in the system.

    Subclass requirements:
        * `agent_name: ClassVar[str]`
        * `agent_version: ClassVar[str]`  # semver
        * `system_prompt: ClassVar[PromptTemplate]`
        * `OutputSchema: ClassVar[type[TOutput]]`
        * `build_user_prompt(self, inputs: TInput) -> str`
    """

    agent_name: ClassVar[str] = "base"
    agent_version: ClassVar[str] = "0.0.0"
    system_prompt: ClassVar[PromptTemplate]
    OutputSchema: ClassVar[type[BaseModel]]

    def __init__(
        self,
        router: LLMRouter,
        *,
        max_repair_attempts: int = 2,
        max_tokens: int | None = None,
    ) -> None:
        self._router = router
        self._max_repair_attempts = max_repair_attempts
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------ Subclass API
    def build_user_prompt(self, inputs: TInput) -> str:  # noqa: ARG002 — override
        raise NotImplementedError

    # ------------------------------------------------------------------ Entry point
    async def run(self, *, tenant_id: TenantId, inputs: TInput) -> AgentResult:
        agent_run_id = AgentRunId(new_id())
        user_prompt = self.build_user_prompt(inputs)
        started = time.perf_counter()
        started_dt = datetime.now(UTC)

        _logger.info(
            "agents.run.started",
            agent_run_id=str(agent_run_id),
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            prompt_template=self.system_prompt.name,
            prompt_template_version=self.system_prompt.version,
            tenant_id=str(tenant_id),
        )

        try:
            validated: ValidatedOutput = await validate_or_repair(
                self._router,
                system_prompt=self.system_prompt.content,
                user_prompt=user_prompt,
                schema=self.OutputSchema,  # type: ignore[arg-type]
                max_repair_attempts=self._max_repair_attempts,
                max_tokens=self._max_tokens,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            telemetry = AgentTelemetry(
                agent_run_id=agent_run_id,
                agent_name=self.agent_name,
                agent_version=self.agent_version,
                prompt_template_name=self.system_prompt.name,
                prompt_template_version=self.system_prompt.version,
                prompt_template_hash=self.system_prompt.content_hash,
                validation_status=ValidationStatus.FAILED,
                repair_attempts=0,
                total_tokens_in=0,
                total_tokens_out=0,
                total_cost_usd=0.0,
                total_latency_ms=elapsed_ms,
                provider_chain=[],
                succeeded=False,
                error=str(exc),
                started_at=started_dt,
                completed_at=datetime.now(UTC),
            )
            _logger.error(
                "agents.run.failed",
                agent_run_id=str(agent_run_id),
                agent_name=self.agent_name,
                error=str(exc),
            )
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        provider_chain, tokens_in, tokens_out, cost_usd, llm_latency_ms = (
            _aggregate_transcript(validated.raw_responses)
        )

        telemetry = AgentTelemetry(
            agent_run_id=agent_run_id,
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            prompt_template_name=self.system_prompt.name,
            prompt_template_version=self.system_prompt.version,
            prompt_template_hash=self.system_prompt.content_hash,
            validation_status=validated.status,
            repair_attempts=validated.attempts,
            total_tokens_in=tokens_in,
            total_tokens_out=tokens_out,
            total_cost_usd=cost_usd,
            total_latency_ms=max(elapsed_ms, llm_latency_ms),
            provider_chain=provider_chain,
            succeeded=True,
            started_at=started_dt,
            completed_at=datetime.now(UTC),
        )

        _logger.info(
            "agents.run.succeeded",
            agent_run_id=str(agent_run_id),
            agent_name=self.agent_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=elapsed_ms,
            repair_attempts=validated.attempts,
            provider_chain=provider_chain,
        )

        return AgentResult(output=validated.parsed, telemetry=telemetry)


def _aggregate_transcript(
    transcript: list[RoutedResponse],
) -> tuple[list[str], int, int, float, int]:
    providers: list[str] = []
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0
    latency_ms = 0
    for routed in transcript:
        for att in routed.attempts:
            providers.append(att.provider.value)
        tokens_in += routed.response.tokens_in
        tokens_out += routed.response.tokens_out
        cost_usd += routed.response.cost_usd
        latency_ms += routed.response.latency_ms
    return providers, tokens_in, tokens_out, cost_usd, latency_ms
