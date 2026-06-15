"""HTTP schemas for the approval queue."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PendingApproval(BaseModel):
    """A recovery awaiting human approval (state=awaiting_approval)."""

    model_config = ConfigDict(from_attributes=True)

    recovery_id: UUID
    tenant_id: UUID
    transaction_id: UUID
    policy_decision_id: UUID | None = None
    reason: str | None = None
    started_at: datetime


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=512)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=512)


class ApprovalDecisionResult(BaseModel):
    """Returned after approving/rejecting."""

    recovery_id: UUID
    new_state: str
    decided_at: datetime
