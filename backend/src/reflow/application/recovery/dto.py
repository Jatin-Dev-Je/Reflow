"""DTOs for the recovery application layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import RecoveryId, TenantId, TransactionId


class StartRecoveryChainCommand(BaseModel):
    """Run the full agent chain (Diagnosis -> Strategy -> Risk -> Policy -> Guard)
    against a failed transaction. Creates a new Recovery aggregate and walks
    the chain synchronously, persisting every step.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: TenantId
    transaction_id: TransactionId
    attempt_number: int = Field(default=1, ge=1)


class RecoveryStepSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    artifact_id: str | None = None
    telemetry: dict[str, Any]


class StartRecoveryChainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovery_id: RecoveryId
    final_state: str
    stopped_reason: str | None = None
    steps: list[RecoveryStepSummary]
