"""HTTP schemas for feature flag + kill switch endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    description: str | None = None
    flag_type: str
    default_value: Any
    is_killswitch: bool
    updated_at: datetime


class EffectiveFlag(BaseModel):
    """A flag's effective value for the current tenant.

    Includes the default and (if present) the tenant override, plus the
    resolved value the application code should read.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    description: str | None = None
    flag_type: str
    default_value: Any
    tenant_override: Any | None = None
    rollout_percent: int | None = None
    resolved_value: Any


class SetTenantFlagBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any
    rollout_percent: int | None = Field(default=None, ge=0, le=100)


class TenantFlagResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    key: str
    value: Any
    rollout_percent: int | None = None
    updated_at: datetime


class KillSwitchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    description: str | None = None
    is_active: bool
    activated_at: datetime | None = None
    activated_by: UUID | None = None
    reason: str | None = None
    updated_at: datetime


class ActivateKillSwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=512)
