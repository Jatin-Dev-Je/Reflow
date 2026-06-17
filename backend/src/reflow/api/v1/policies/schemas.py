"""HTTP schemas for policy CRUD."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = None
    name: str
    description: str | None = None
    status: str
    current_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CreatePolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class UpdatePolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, description="draft / active / retired")


class PolicyVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_id: UUID
    version: int
    rules: Any
    rules_hash: str
    notes: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None


class CreateVersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: Any = Field(description="JSON rule set — validated server-side.")
    notes: str | None = Field(default=None, max_length=512)


class SimulateVersionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_days: int = Field(default=7, ge=1, le=90)


class SimulateVersionResult(BaseModel):
    """Diff between current policy decisions and what the candidate version
    would have decided, over a historical window."""

    model_config = ConfigDict(extra="forbid")

    window_days: int
    decisions_evaluated: int
    decisions_changed: int
    change_breakdown: dict[str, int]
