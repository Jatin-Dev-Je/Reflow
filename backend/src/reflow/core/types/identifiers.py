"""Typed identifiers.

A `TenantId` is not a `TransactionId`. The type system must reflect that, even
though both are UUIDs underneath. Phantom types (NewType) give us compile-time
safety without runtime overhead — passing a `TenantId` where a `TransactionId`
is required becomes a type error.
"""

from __future__ import annotations

from typing import Annotated, NewType
from uuid import UUID, uuid4

from pydantic import AfterValidator

TenantId = NewType("TenantId", UUID)
UserId = NewType("UserId", UUID)
TransactionId = NewType("TransactionId", UUID)
AttemptId = NewType("AttemptId", UUID)
RecoveryId = NewType("RecoveryId", UUID)
DiagnosisId = NewType("DiagnosisId", UUID)
StrategyId = NewType("StrategyId", UUID)
RiskAssessmentId = NewType("RiskAssessmentId", UUID)
PolicyId = NewType("PolicyId", UUID)
PolicyVersionId = NewType("PolicyVersionId", UUID)
PolicyDecisionId = NewType("PolicyDecisionId", UUID)
ApprovalId = NewType("ApprovalId", UUID)
ExecutionAttemptId = NewType("ExecutionAttemptId", UUID)
EventId = NewType("EventId", UUID)
AgentRunId = NewType("AgentRunId", UUID)
LlmCallId = NewType("LlmCallId", UUID)
CommandId = NewType("CommandId", UUID)
CorrelationId = NewType("CorrelationId", UUID)
CausationId = NewType("CausationId", UUID)


def _ensure_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)


UuidField = Annotated[UUID, AfterValidator(_ensure_uuid)]


def new_id() -> UUID:
    """Generate a fresh UUID. Centralized so we can swap to UUID v7 later."""
    return uuid4()


def new_tenant_id() -> TenantId:
    return TenantId(new_id())


def new_transaction_id() -> TransactionId:
    return TransactionId(new_id())


def new_recovery_id() -> RecoveryId:
    return RecoveryId(new_id())


def new_event_id() -> EventId:
    return EventId(new_id())


def new_command_id() -> CommandId:
    return CommandId(new_id())


def new_correlation_id() -> CorrelationId:
    return CorrelationId(new_id())
