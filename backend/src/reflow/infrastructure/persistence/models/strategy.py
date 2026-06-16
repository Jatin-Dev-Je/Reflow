"""ORM model for agent.strategies."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class StrategyModel(Base):
    __tablename__ = "strategies"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('immediate_retry','delayed_retry','gateway_reroute',"
            "'rail_switch','payment_link_nudge','graceful_failure','manual_review')",
            name="strategies_action_type_check",
        ),
        CheckConstraint(
            "expected_recovery_probability IS NULL OR "
            "(expected_recovery_probability >= 0 AND expected_recovery_probability <= 1)",
            name="strategies_probability_range",
        ),
        Index("ix_strat_diag", "diagnosis_id"),
        Index("ix_strat_tenant_action", "tenant_id", "action_type", "created_at"),
        {"schema": "agent"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    diagnosis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.diagnoses.id"), nullable=False
    )

    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    expected_recovery_probability: Mapped[float | None] = mapped_column(Numeric(3, 2))
    expected_revenue_cents: Mapped[int | None] = mapped_column(BigInteger)
    expected_latency_seconds: Mapped[int | None] = mapped_column(Integer)

    rationale: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
