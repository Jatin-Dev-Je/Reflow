"""HTTP schemas for observability endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = None
    agent_name: str
    agent_version: str
    recovery_id: UUID | None = None
    transaction_id: UUID | None = None
    parent_run_id: UUID | None = None
    trace_id: str | None = None
    span_id: str | None = None
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    total_cost_usd: float
    total_tokens_in: int
    total_tokens_out: int
    total_calls: int
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None


class LlmCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_run_id: UUID | None = None
    provider: str
    model: str
    prompt_template_id: UUID | None = None
    prompt_hash: str
    cache_hit: bool
    fallback_from: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    validation_status: str | None = None
    validation_attempts: int
    called_at: datetime


class CostBreakdownEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_value: str
    runs: int = Field(ge=0)
    total_cost_usd: float = Field(ge=0)
    total_tokens_in: int = Field(ge=0)
    total_tokens_out: int = Field(ge=0)
    avg_latency_ms: int | None = None


class CostBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: int = Field(gt=0)
    grand_total_usd: float = Field(ge=0)
    grand_total_runs: int = Field(ge=0)
    by_agent: list[CostBreakdownEntry]
    by_provider: list[CostBreakdownEntry]
