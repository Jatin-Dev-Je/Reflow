"""HTTP routes for the recovery context."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from pydantic import BaseModel, ConfigDict, Field

from reflow.api.deps import CoordinatorDep, CurrentTenant, SessionDep
from reflow.api.v1.recoveries.schemas import (
    RecoveryExecutionAttemptRead,
    RecoveryRead,
    RecoveryStepRead,
)
from reflow.application.recovery import (
    StartRecoveryChainCommand,
    StartRecoveryChainHandler,
    StartRecoveryChainResult,
)
from reflow.core.types import TransactionId
from reflow.domain.recovery import RecoveryState
from reflow.infrastructure.persistence.models import (
    RecoveryExecutionAttemptModel,
    RecoveryModel,
    RecoveryStepModel,
)

router = APIRouter(prefix="/recoveries", tags=["recoveries"])

PAGE_DEFAULT = 50
PAGE_MAX = 200


class StartRecoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: TransactionId
    attempt_number: int = Field(default=1, ge=1)


@router.post(
    "/start",
    response_model=StartRecoveryChainResult,
    summary="Run the full agent chain for a failed transaction",
)
async def start_recovery(
    body: StartRecoveryBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
    coordinator: CoordinatorDep,
) -> StartRecoveryChainResult:
    handler = StartRecoveryChainHandler(session=session, coordinator=coordinator)
    return await handler.handle(
        StartRecoveryChainCommand(
            tenant_id=tenant_id,
            transaction_id=body.transaction_id,
            attempt_number=body.attempt_number,
        )
    )


@router.get(
    "",
    response_model=list[RecoveryRead],
    summary="List recoveries",
)
async def list_recoveries(
    session: SessionDep,
    tenant_id: CurrentTenant,
    state_filter: Annotated[
        RecoveryState | None,
        Query(alias="state", description="Filter by recovery state."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[RecoveryRead]:
    stmt = (
        select(RecoveryModel)
        .where(RecoveryModel.tenant_id == tenant_id)
        .order_by(desc(RecoveryModel.started_at))
        .limit(limit)
    )
    if state_filter is not None:
        stmt = stmt.where(RecoveryModel.state == state_filter.value)
    rows = (await session.execute(stmt)).scalars().all()
    return [RecoveryRead.model_validate(r) for r in rows]


async def _load_recovery(
    session: SessionDep, recovery_id: UUID, tenant_id: UUID
) -> RecoveryModel:
    row = await session.get(RecoveryModel, recovery_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recovery not found"
        )
    return row


@router.get(
    "/{recovery_id}",
    response_model=RecoveryRead,
    summary="Get a single recovery saga",
)
async def get_recovery(
    recovery_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> RecoveryRead:
    row = await _load_recovery(session, recovery_id, tenant_id)
    return RecoveryRead.model_validate(row)


@router.get(
    "/{recovery_id}/steps",
    response_model=list[RecoveryStepRead],
    summary="List saga step transitions",
)
async def get_recovery_steps(
    recovery_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> list[RecoveryStepRead]:
    await _load_recovery(session, recovery_id, tenant_id)
    stmt = (
        select(RecoveryStepModel)
        .where(RecoveryStepModel.recovery_id == recovery_id)
        .order_by(RecoveryStepModel.step_number)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [RecoveryStepRead.model_validate(r) for r in rows]


@router.get(
    "/{recovery_id}/executions",
    response_model=list[RecoveryExecutionAttemptRead],
    summary="List gateway execution attempts",
)
async def get_recovery_executions(
    recovery_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> list[RecoveryExecutionAttemptRead]:
    await _load_recovery(session, recovery_id, tenant_id)
    stmt = (
        select(RecoveryExecutionAttemptModel)
        .where(RecoveryExecutionAttemptModel.recovery_id == recovery_id)
        .order_by(RecoveryExecutionAttemptModel.attempt_number)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [RecoveryExecutionAttemptRead.model_validate(r) for r in rows]
