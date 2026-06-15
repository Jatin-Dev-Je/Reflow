"""HTTP schemas for recovery endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from reflow.domain.recovery import RecoveryState


class RecoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    transaction_id: UUID
    state: RecoveryState
    diagnosis_id: UUID | None = None
    strategy_id: UUID | None = None
    risk_assessment_id: UUID | None = None
    policy_decision_id: UUID | None = None
    approval_id: UUID | None = None
    recovery_key: str
    outcome: str | None = None
    recovered_amount_cents: int | None = None
    recovery_latency_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    next_action_at: datetime | None = None
    last_error: str | None = None
    retry_count: int


class RecoveryStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_number: int
    from_state: str
    to_state: str
    triggered_by: str
    handler: str | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None


class RecoveryExecutionAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_number: int
    gateway_id: str
    idempotency_key: str
    outcome: str | None = None
    decline_code: str | None = None
    latency_ms: int | None = None
    cost_cents: int | None = None
    attempted_at: datetime
    completed_at: datetime | None = None
