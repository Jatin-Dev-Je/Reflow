"""ORM models for core.users + core.user_tenant_roles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from reflow.core.database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = ({"schema": "core"},)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(Text)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class UserTenantRoleModel(Base):
    __tablename__ = "user_tenant_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','operator','viewer','approver')",
            name="user_tenant_roles_role_check",
        ),
        {"schema": "core"},
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("core.tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    granted_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
