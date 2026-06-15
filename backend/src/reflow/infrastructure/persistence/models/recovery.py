"""ORM models for the recovery schema.

Tables mirror the DDL in 001_initial_schema.sql:
    * recovery.recoveries          — the saga aggregate read model
    * recovery.steps               — every state transition
    * recovery.execution_attempts  — gateway calls; UNIQUE(gateway_id, idempotency_key)
                                     is the zero-double-charge guarantee
"""

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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class RecoveryModel(Base):
    __tablename__ = "recoveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "recovery_key", name="recoveries_tenant_key_unique"),
        CheckConstraint(
            "state IN ('created','diagnosed','strategy_proposed','risk_assessed',"
            "'policy_evaluated','awaiting_approval','approved','executing',"
            "'executed','compensating','recovered','failed','abandoned')",
            name="recoveries_state_check",
        ),
        Index(
            "ix_recoveries_due",
            "next_action_at",
            postgresql_where=text(
                "state NOT IN ('recovered','failed','abandoned') "
                "AND next_action_at IS NOT NULL"
            ),
        ),
        Index("ix_recoveries_tenant_state_time", "tenant_id", "state", "started_at"),
        Index("ix_recoveries_transaction", "transaction_id"),
        {"schema": "recovery"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    state: Mapped[str] = mapped_column(String(32), nullable=False, default="created")

    diagnosis_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    strategy_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    risk_assessment_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    policy_decision_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    approval_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

    recovery_key: Mapped[str] = mapped_column(Text, nullable=False)
    execution_token: Mapped[str | None] = mapped_column(Text)

    outcome: Mapped[str | None] = mapped_column(String(32))
    recovered_amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    recovery_latency_ms: Mapped[int | None] = mapped_column(Integer)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RecoveryStepModel(Base):
    __tablename__ = "steps"
    __table_args__ = (
        UniqueConstraint(
            "recovery_id", "step_number", name="recovery_steps_step_number_unique"
        ),
        Index("ix_steps_recovery_time", "recovery_id", "started_at"),
        {"schema": "recovery"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    recovery_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recovery.recoveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)

    from_state: Mapped[str] = mapped_column(Text, nullable=False)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    handler: Mapped[str | None] = mapped_column(Text)

    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class RecoveryExecutionAttemptModel(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        # The zero-double-charge guarantee.
        UniqueConstraint(
            "gateway_id", "idempotency_key", name="execution_attempts_gateway_key_unique"
        ),
        UniqueConstraint(
            "recovery_id", "attempt_number", name="execution_attempts_recovery_number_unique"
        ),
        CheckConstraint("attempt_number >= 1", name="execution_attempts_number_positive"),
        Index("ix_exec_recovery", "recovery_id", "attempt_number"),
        Index("ix_exec_gateway_time", "gateway_id", "attempted_at"),
        {"schema": "recovery"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    recovery_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recovery.recoveries.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    gateway_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)

    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    outcome: Mapped[str | None] = mapped_column(String(32))
    decline_code: Mapped[str | None] = mapped_column(Text)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_cents: Mapped[int | None] = mapped_column(Integer)

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
