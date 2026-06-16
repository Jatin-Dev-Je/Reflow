"""ORM models for feature flags + kill switches."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class FeatureFlagModel(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (
        CheckConstraint(
            "flag_type IN ('boolean','string','number','json')",
            name="feature_flags_type_check",
        ),
        {"schema": "flags"},
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    default_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    is_killswitch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TenantFlagModel(Base):
    __tablename__ = "tenant_flags"
    __table_args__ = (
        CheckConstraint(
            "rollout_percent IS NULL OR (rollout_percent >= 0 AND rollout_percent <= 100)",
            name="tenant_flags_rollout_range",
        ),
        {"schema": "flags"},
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    key: Mapped[str] = mapped_column(
        Text, ForeignKey("flags.feature_flags.key"), primary_key=True
    )
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    rollout_percent: Mapped[int | None] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class KillSwitchModel(Base):
    __tablename__ = "kill_switches"
    __table_args__ = ({"schema": "flags"},)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
