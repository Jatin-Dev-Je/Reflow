"""ORM models for agent.diagnoses + agent.evidence_items."""

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
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class DiagnosisModel(Base):
    __tablename__ = "diagnoses"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="diagnoses_confidence_range"
        ),
        CheckConstraint(
            "root_cause_category IN ('issuer_outage','issuer_decline','gateway_degraded',"
            "'gateway_outage','network','authentication','fraud_signal',"
            "'insufficient_funds','other')",
            name="diagnoses_root_cause_category_check",
        ),
        Index("ix_diag_tx", "transaction_id"),
        Index("ix_diag_tenant", "tenant_id", "root_cause_category", "created_at"),
        Index("ix_diag_attempt", "attempt_id"),
        {"schema": "agent"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_category: Mapped[str] = mapped_column(Text, nullable=False)
    is_recoverable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)

    agent_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    prompt_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(Text)

    reasoning: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EvidenceItemModel(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint(
            "diagnosis_id", "citation_index", name="evidence_items_diagnosis_index_unique"
        ),
        CheckConstraint(
            "evidence_type IN ('historical_recovery','gateway_health','issuer_health',"
            "'pattern_match','similar_failure','rule_match','external_signal')",
            name="evidence_items_type_check",
        ),
        CheckConstraint("citation_index >= 1", name="evidence_items_index_positive"),
        {"schema": "agent"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    diagnosis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent.diagnoses.id", ondelete="CASCADE"),
        nullable=False,
    )
    citation_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_table: Mapped[str | None] = mapped_column(Text)
    source_query: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    observation: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    weight: Mapped[float | None] = mapped_column(Numeric(3, 2))

    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
