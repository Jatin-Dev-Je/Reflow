"""ORM models for the txn schema (transactions + attempts).

These are the *read models* — derived from the event stream. The aggregate
writes to the event store; this projection is kept in sync synchronously
within the same transaction for single-aggregate reads (the most common
hot path).
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
from sqlalchemy.dialects.postgresql import CHAR, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="transactions_tenant_external_unique"),
        CheckConstraint(
            "status IN ('pending','succeeded','failed','recovering','recovered','abandoned')",
            name="transactions_status_check",
        ),
        CheckConstraint("amount_cents > 0", name="transactions_amount_positive"),
        Index("ix_txn_tenant_status_created", "tenant_id", "status", "created_at"),
        Index(
            "ix_txn_tenant_issuer_failing",
            "tenant_id",
            "issuer_id",
            "status",
            postgresql_where=text("status IN ('failed','recovering')"),
        ),
        {"schema": "txn"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    customer_ref: Mapped[str | None] = mapped_column(Text)

    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)

    card_bin: Mapped[str | None] = mapped_column(CHAR(6))
    card_last4: Mapped[str | None] = mapped_column(CHAR(4))
    card_brand: Mapped[str | None] = mapped_column(Text)
    card_funding: Mapped[str | None] = mapped_column(Text)
    card_country: Mapped[str | None] = mapped_column(CHAR(2))

    issuer_id: Mapped[str | None] = mapped_column(Text)
    gateway_id: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    initial_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transaction_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AttemptModel(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        UniqueConstraint("transaction_id", "attempt_number", name="attempts_txn_number_unique"),
        CheckConstraint("attempt_number >= 1", name="attempts_number_positive"),
        CheckConstraint(
            "outcome IN ('success','soft_decline','hard_decline','error','timeout')",
            name="attempts_outcome_check",
        ),
        Index("ix_attempts_tenant_gateway_time", "tenant_id", "gateway_id", "attempted_at"),
        Index(
            "ix_attempts_tenant_decline_time",
            "tenant_id",
            "decline_code_normalized",
            "attempted_at",
            postgresql_where=text("outcome IN ('soft_decline','hard_decline')"),
        ),
        {"schema": "txn"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("txn.transactions.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    gateway_id: Mapped[str] = mapped_column(Text, nullable=False)
    gateway_request_id: Mapped[str | None] = mapped_column(Text)
    gateway_response_id: Mapped[str | None] = mapped_column(Text)

    outcome: Mapped[str] = mapped_column(String(32), nullable=False)

    decline_code: Mapped[str | None] = mapped_column(Text)
    decline_code_normalized: Mapped[str | None] = mapped_column(Text)
    decline_category: Mapped[str | None] = mapped_column(Text)
    decline_message: Mapped[str | None] = mapped_column(Text)

    network_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
