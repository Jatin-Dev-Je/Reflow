"""ORM model for policy.decisions (read-only from this codebase's view).

We don't model policy.policies or policy.policy_versions here yet — the
default policy is built in-code (see ADR-0003). When dynamic policy editing
lands, those tables get ORM models too.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class PolicyDecisionModel(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('allow','deny','require_approval')",
            name="policy_decisions_decision_check",
        ),
        Index("ix_decisions_tenant_time", "tenant_id", "decided_at"),
        Index("ix_decisions_recovery", "recovery_id"),
        Index("ix_decisions_strategy", "strategy_id"),
        Index(
            "ix_decisions_version_outcome",
            "policy_version_id",
            "decision",
        ),
        {"schema": "policy"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    recovery_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    strategy_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    policy_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    decision: Mapped[str] = mapped_column(Text, nullable=False)
    matched_rule_id: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
