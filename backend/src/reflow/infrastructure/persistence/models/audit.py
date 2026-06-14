"""ORM model for audit.chain_anchors."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class ChainAnchorModel(Base):
    __tablename__ = "chain_anchors"
    __table_args__ = (
        CheckConstraint("end_sequence >= start_sequence", name="chain_anchors_range_check"),
        Index("ix_chain_anchors_tenant_signed", "tenant_id", "signed_at"),
        Index("ix_chain_anchors_range", "start_sequence", "end_sequence"),
        {"schema": "audit"},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))  # NULL = global
    start_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    merkle_root: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
