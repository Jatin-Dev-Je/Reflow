"""LLM client — provider-agnostic wrapper around LiteLLM.

Responsibilities:
    * One call interface across Groq / Gemini / OpenRouter / Cerebras.
    * Per-call cost computation from usage tokens (best-effort — providers
      vary in reporting).
    * Latency and token telemetry surfaced for the caller to persist.
    * Structured logging that never includes the prompt or completion text
      verbatim (PII risk + token bloat).

The router (see `router.py`) decides which provider to call and handles
fallback. This module is the wire layer only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

import litellm
from litellm.exceptions import APIConnectionError, RateLimitError, Timeout
from pydantic import SecretStr

from reflow.core.config import LLMKeys, LLMProvider, LLMSettings
from reflow.core.exceptions import (
    CircuitBreakerOpenError,
    DependencyTimeoutError,
    LLMError,
)
from reflow.core.observability.logging import get_logger
from reflow.core.security.signing import sha256_hex

_logger = get_logger(__name__)


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    FILTER = "content_filter"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class LLMRequest:
    provider: LLMProvider
    model: str
    system_prompt: str
    user_prompt: str
    max_tokens: int
    temperature: float = 0.0
    json_mode: bool = True   # we expect structured outputs almost everywhere
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Provider-agnostic response shape."""

    content: str
    provider: LLMProvider
    model: str
    finish_reason: FinishReason
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    prompt_hash: str


def _api_key_for(provider: LLMProvider, keys: LLMKeys) -> SecretStr | None:
    return {
        LLMProvider.GROQ: keys.groq_api_key,
        LLMProvider.GEMINI: keys.gemini_api_key,
        LLMProvider.OPENROUTER: keys.openrouter_api_key,
        LLMProvider.CEREBRAS: keys.cerebras_api_key,
    }.get(provider)


def _model_for(provider: LLMProvider, settings: LLMSettings) -> str:
    return {
        LLMProvider.GROQ: settings.groq_model,
        LLMProvider.GEMINI: settings.gemini_model,
        LLMProvider.OPENROUTER: settings.openrouter_model,
        LLMProvider.CEREBRAS: settings.cerebras_model,
    }[provider]


def _compute_cost_usd(_provider: LLMProvider, response: dict) -> float:
    """Best-effort cost computation. Returns 0.0 on free tiers or unknown models."""
    try:
        cost = litellm.completion_cost(completion_response=response) or 0.0
        return float(cost)
    except Exception:  # noqa: BLE001 — cost is non-critical, never crash on it
        return 0.0


class LLMClient:
    """Thin wrapper around litellm.acompletion with strict typing.

    No retries, no fallback, no circuit breaker — those belong to the router.
    This class just translates between our types and the provider call.
    """

    def __init__(self, settings: LLMSettings, keys: LLMKeys) -> None:
        self._settings = settings
        self._keys = keys

    async def complete(self, req: LLMRequest) -> LLMResponse:
        api_key = _api_key_for(req.provider, self._keys)
        if api_key is None:
            raise LLMError(
                f"No API key configured for provider {req.provider.value!r}",
                context={"provider": req.provider.value},
            )

        # Stable hash for prompt cache + observability — we only log the hash,
        # never the prompt text itself.
        prompt_hash = sha256_hex((req.system_prompt + "\0" + req.user_prompt).encode("utf-8"))

        kwargs: dict = {
            "model": req.model,
            "messages": [
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt},
            ],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "api_key": api_key.get_secret_value(),
            "timeout": req.timeout_seconds or self._settings.request_timeout_seconds,
        }
        if req.json_mode:
            # Most providers honour this; for those that don't, the prompt should
            # still ask for JSON and we'll repair via output_validator.
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            raw = await litellm.acompletion(**kwargs)
        except (RateLimitError, APIConnectionError) as exc:
            raise CircuitBreakerOpenError(
                f"LLM provider {req.provider.value!r} unavailable",
                context={"provider": req.provider.value},
            ) from exc
        except Timeout as exc:
            raise DependencyTimeoutError(
                f"LLM provider {req.provider.value!r} timed out",
                context={"provider": req.provider.value},
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"LLM provider {req.provider.value!r} failed: {exc}",
                context={"provider": req.provider.value, "error": str(exc)},
            ) from exc
        latency_ms = int((time.perf_counter() - start) * 1000)

        # Defensive accessors — litellm returns a ModelResponse object that
        # quacks like a dict.
        choice = raw["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        finish_str = (choice.get("finish_reason") or "stop").lower()
        try:
            finish = FinishReason(finish_str)
        except ValueError:
            finish = FinishReason.OTHER

        usage = raw.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        cost_usd = _compute_cost_usd(req.provider, dict(raw))

        _logger.info(
            "llm.call",
            provider=req.provider.value,
            model=req.model,
            prompt_hash=prompt_hash,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            finish_reason=finish.value,
        )

        return LLMResponse(
            content=content,
            provider=req.provider,
            model=req.model,
            finish_reason=finish,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            prompt_hash=prompt_hash,
        )
