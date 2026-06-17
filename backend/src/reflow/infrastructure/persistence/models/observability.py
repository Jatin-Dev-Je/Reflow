"""ORM models for obs.agent_runs, obs.llm_calls, obs.prompt_templates."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class PromptTemplateModel(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="prompt_templates_name_version_unique"),
        CheckConstraint("version >= 1", name="prompt_templates_version_positive"),
        Index(
            "ix_prompts_active", "name", postgresql_where=text("is_active = true")
        ),
        {"schema": "obs"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    template_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AgentRunModel(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started','succeeded','failed','timeout','cancelled')",
            name="agent_runs_status_check",
        ),
        Index("ix_agent_runs_tenant_agent_time", "tenant_id", "agent_name", "started_at"),
        Index("ix_agent_runs_recovery", "recovery_id"),
        Index("ix_agent_runs_trace", "trace_id"),
        Index(
            "ix_agent_runs_status_time",
            "status",
            "started_at",
            postgresql_where=text("status IN ('failed','timeout')"),
        ),
        {"schema": "obs"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)

    recovery_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    transaction_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    parent_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    trace_id: Mapped[str | None] = mapped_column(Text)
    span_id: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(Text, nullable=False)

    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    total_tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class LlmCallModel(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        CheckConstraint(
            "validation_status IS NULL OR "
            "validation_status IN ('valid','repaired','failed')",
            name="llm_calls_validation_check",
        ),
        Index("ix_llm_calls_agent_run", "agent_run_id"),
        Index("ix_llm_calls_provider_time", "provider", "called_at"),
        Index(
            "ix_llm_calls_cache_hit",
            "called_at",
            postgresql_where=text("cache_hit = true"),
        ),
        Index("ix_llm_calls_prompt_hash", "prompt_hash"),
        {"schema": "obs"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("obs.agent_runs.id", ondelete="CASCADE"),
    )

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("obs.prompt_templates.id")
    )
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)

    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_from: Mapped[str | None] = mapped_column(Text)

    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    validation_status: Mapped[str | None] = mapped_column(Text)
    validation_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )

    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
