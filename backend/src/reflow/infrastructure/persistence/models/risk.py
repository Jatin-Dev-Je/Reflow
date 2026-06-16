"""ORM model for agent.risk_assessments."""

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
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class RiskAssessmentModel(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint(
            "financial_risk_score >= 0 AND financial_risk_score <= 1",
            name="risk_financial_range",
        ),
        CheckConstraint(
            "operational_risk_score >= 0 AND operational_risk_score <= 1",
            name="risk_operational_range",
        ),
        CheckConstraint(
            "customer_friction_score >= 0 AND customer_friction_score <= 1",
            name="risk_friction_range",
        ),
        CheckConstraint(
            "duplicate_charge_probability >= 0 AND duplicate_charge_probability <= 1",
            name="risk_dup_probability_range",
        ),
        CheckConstraint(
            "overall_risk_level IN ('low','medium','high','critical')",
            name="risk_level_check",
        ),
        Index("ix_risk_strategy", "strategy_id"),
        Index("ix_risk_level", "tenant_id", "overall_risk_level", "created_at"),
        {"schema": "agent"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    strategy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent.strategies.id"), nullable=False
    )

    financial_risk_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    operational_risk_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    customer_friction_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    duplicate_charge_probability: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)

    overall_risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    expected_revenue_impact_cents: Mapped[int | None] = mapped_column(BigInteger)
    factors: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    agent_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
