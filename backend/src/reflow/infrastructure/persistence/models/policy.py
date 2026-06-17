"""ORM models for policy.policies, policy.policy_versions, policy.decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class PolicyModel(Base):
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="policies_tenant_name_unique"),
        CheckConstraint(
            "status IN ('draft','active','retired')",
            name="policies_status_check",
        ),
        {"schema": "policy"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.tenants.id"),
    )  # NULL = global default
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    current_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PolicyVersionModel(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "policy_id", "version", name="policy_versions_policy_version_unique"
        ),
        CheckConstraint("version >= 1", name="policy_versions_version_positive"),
        Index(
            "ix_policy_versions_active",
            "policy_id",
            postgresql_where=text("activated_at IS NOT NULL AND deactivated_at IS NULL"),
        ),
        {"schema": "policy"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    policy_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy.policies.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rules: Mapped[Any] = mapped_column(JSONB, nullable=False)
    rules_hash: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
