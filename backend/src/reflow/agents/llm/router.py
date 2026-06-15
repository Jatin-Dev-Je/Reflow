"""LLM provider router — primary, fallback, emergency.

The router owns the policy of *which* provider gets called and what happens
when it fails. The client (`client.py`) owns the wire call. This separation
means provider configuration changes never touch agent code.

Failure semantics:
    * RateLimitError / connection failure -> try next provider in chain.
    * Timeout                              -> try next provider.
    * Schema validation failure            -> repaired by the agent layer,
                                              not retried here.
    * Cost-cap exceeded                    -> NEVER retried; raise immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reflow.core.config import LLMKeys, LLMProvider, LLMSettings, get_settings
from reflow.core.exceptions import (
    CircuitBreakerOpenError,
    DependencyTimeoutError,
    LLMError,
)
from reflow.core.observability.logging import get_logger
from reflow.agents.llm.client import LLMClient, LLMRequest, LLMResponse

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RouteAttempt:
    """One try in a routed call. Surfaced so the agent can record the
    fallback chain in audit telemetry."""

    provider: LLMProvider
    model: str
    error: str | None


@dataclass(frozen=True, slots=True)
class RoutedResponse:
    """Final response plus the chain of attempts taken to get it."""

    response: LLMResponse
    attempts: list[RouteAttempt] = field(default_factory=list)


class LLMRouter:
    def __init__(
        self,
        settings: LLMSettings | None = None,
        keys: LLMKeys | None = None,
    ) -> None:
        cfg = get_settings()
        self._settings = settings or cfg.llm
        self._keys = keys or cfg.llm_keys
        self._client = LLMClient(self._settings, self._keys)

    def _model_for(self, provider: LLMProvider) -> str:
        return {
            LLMProvider.GROQ: self._settings.groq_model,
            LLMProvider.GEMINI: self._settings.gemini_model,
            LLMProvider.OPENROUTER: self._settings.openrouter_model,
            LLMProvider.CEREBRAS: self._settings.cerebras_model,
        }[provider]

    def _chain(self) -> list[LLMProvider]:
        # Order matters; de-duped while preserving order.
        seen: set[LLMProvider] = set()
        out: list[LLMProvider] = []
        for p in [
            self._settings.primary_provider,
            self._settings.fallback_provider,
            self._settings.emergency_provider,
        ]:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        json_mode: bool = True,
        timeout_seconds: float | None = None,
    ) -> RoutedResponse:
        attempts: list[RouteAttempt] = []
        last_exc: BaseException | None = None

        for provider in self._chain():
            model = self._model_for(provider)
            req = LLMRequest(
                provider=provider,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens or self._settings.max_tokens_per_call,
                temperature=temperature,
                json_mode=json_mode,
                timeout_seconds=timeout_seconds,
            )
            try:
                resp = await self._client.complete(req)
            except (CircuitBreakerOpenError, DependencyTimeoutError, LLMError) as exc:
                attempts.append(
                    RouteAttempt(provider=provider, model=model, error=str(exc))
                )
                last_exc = exc
                _logger.warning(
                    "llm.router.fallback",
                    failed_provider=provider.value,
                    error=str(exc),
                )
                continue

            attempts.append(RouteAttempt(provider=provider, model=model, error=None))
            return RoutedResponse(response=resp, attempts=attempts)

        # All providers exhausted.
        raise LLMError(
            "All configured LLM providers failed",
            context={"attempts": [a.provider.value for a in attempts]},
        ) from last_exc
