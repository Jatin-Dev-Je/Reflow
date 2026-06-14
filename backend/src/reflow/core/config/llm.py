"""LLM provider settings.

Reflow uses LiteLLM to abstract provider calls. We configure a primary +
fallback chain — Groq first (fast), Gemini next (reliable), OpenRouter last
(emergency). All free tiers; see ADR-0004 for the tiered intelligence model.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    GROQ = "groq"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    CEREBRAS = "cerebras"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", extra="ignore")

    primary_provider: LLMProvider = Field(default=LLMProvider.GROQ)
    fallback_provider: LLMProvider = Field(default=LLMProvider.GEMINI)
    emergency_provider: LLMProvider = Field(default=LLMProvider.OPENROUTER)

    # Model identifiers per provider (LiteLLM-compatible).
    groq_model: str = Field(default="groq/llama-3.3-70b-versatile")
    gemini_model: str = Field(default="gemini/gemini-2.0-flash-exp")
    openrouter_model: str = Field(default="openrouter/meta-llama/llama-3.3-70b-instruct:free")
    cerebras_model: str = Field(default="cerebras/llama-3.3-70b")

    # Token + cost budgets (per single agent call, not per saga).
    max_tokens_per_call: int = Field(default=2048, gt=0)
    request_timeout_seconds: float = Field(default=10.0, gt=0)
    max_repair_attempts: int = Field(
        default=2,
        ge=0,
        le=5,
        description="How many times to re-prompt after schema validation failure.",
    )

    # Response cache.
    cache_ttl_seconds: int = Field(default=3600, ge=0)

    # Embedding model — runs locally via fastembed, no network call.
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_dim: int = Field(default=384, gt=0)


class LLMKeys(BaseSettings):
    """LLM provider API keys — separated so they can be sourced from a secrets
    manager in production while non-secret config stays in env."""

    model_config = SettingsConfigDict(extra="ignore")

    groq_api_key: SecretStr | None = Field(default=None)
    gemini_api_key: SecretStr | None = Field(default=None)
    openrouter_api_key: SecretStr | None = Field(default=None)
    cerebras_api_key: SecretStr | None = Field(default=None)
