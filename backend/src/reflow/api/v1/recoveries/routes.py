"""HTTP routes for the recovery context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from pydantic import BaseModel, ConfigDict, Field

from reflow.api.deps import CoordinatorDep, CurrentTenant, SessionDep
from reflow.api.v1.recoveries.schemas import (
    RecoveryExecutionAttemptRead,
    RecoveryRead,
    RecoveryStepRead,
)
from reflow.api.v1.transactions.schemas import RecoveryStats
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
    "/stats",
    response_model=RecoveryStats,
    summary="Aggregate recovery stats over a recent window",
)
async def recovery_stats(
    session: SessionDep,
    tenant_id: CurrentTenant,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> RecoveryStats:
    end = datetime.now(UTC)
    start = end - timedelta(days=window_days)

    # By state.
    state_stmt = (
        select(RecoveryModel.state, func.count().label("n"))
        .where(RecoveryModel.tenant_id == tenant_id)
        .where(RecoveryModel.started_at >= start)
        .where(RecoveryModel.started_at < end)
        .group_by(RecoveryModel.state)
    )
    state_rows = (await session.execute(state_stmt)).all()
    by_state: dict[str, int] = {r.state: int(r.n) for r in state_rows}
    total = sum(by_state.values())

    # By outcome + recovered totals.
    outcome_stmt = (
        select(
            func.coalesce(RecoveryModel.outcome, "in_flight").label("o"),
            func.count().label("n"),
            func.coalesce(
                func.sum(RecoveryModel.recovered_amount_cents).filter(
                    RecoveryModel.outcome == "recovered"
                ),
                0,
            ).label("revenue"),
            func.coalesce(
                func.avg(RecoveryModel.recovery_latency_ms).filter(
                    RecoveryModel.outcome == "recovered"
                ),
                None,
            ).label("avg_latency"),
        )
        .where(RecoveryModel.tenant_id == tenant_id)
        .where(RecoveryModel.started_at >= start)
        .where(RecoveryModel.started_at < end)
        .group_by(func.coalesce(RecoveryModel.outcome, "in_flight"))
    )
    outcome_rows = (await session.execute(outcome_stmt)).all()
    by_outcome: dict[str, int] = {}
    total_recovered_cents = 0
    avg_latency: float | None = None
    for r in outcome_rows:
        by_outcome[r.o] = int(r.n)
        if r.o == "recovered":
            total_recovered_cents = int(r.revenue or 0)
            avg_latency = float(r.avg_latency) if r.avg_latency is not None else None

    recovered = by_outcome.get("recovered", 0)
    recovery_rate = (recovered / total) if total else 0.0

    return RecoveryStats(
        window_days=window_days,
        total=total,
        by_state=by_state,
        by_outcome=by_outcome,
        recovery_rate=recovery_rate,
        avg_recovery_latency_ms=int(avg_latency) if avg_latency is not None else None,
        total_recovered_cents=total_recovered_cents,
    )


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


# -------------------------------------------------------------- Cancel / Retry


class CancelRecoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=512)


class RetryRecoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_number: int = Field(default=2, ge=1)


@router.post(
    "/{recovery_id}/cancel",
    response_model=RecoveryRead,
    summary="Cancel an in-flight recovery (abandons it with a reason)",
)
async def cancel_recovery(
    recovery_id: UUID,
    body: CancelRecoveryBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> RecoveryRead:
    from reflow.core.events.event import EventMetadata
    from reflow.core.types import RecoveryId
    from reflow.infrastructure.persistence.repositories import SqlRecoveryRepository

    repo = SqlRecoveryRepository(session)
    recovery = await repo.load(RecoveryId(recovery_id))
    if recovery is None or recovery.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recovery not found"
        )
    if recovery.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recovery already in terminal state '{recovery.state.value}'",
        )

    recovery.abandon(
        reason=body.reason,
        metadata=EventMetadata(source="api:recoveries.cancel"),
    )
    await repo.save(recovery)

    row = await session.get(RecoveryModel, recovery_id)
    return RecoveryRead.model_validate(row)


@router.post(
    "/{recovery_id}/retry",
    response_model=StartRecoveryChainResult,
    summary="Start a fresh recovery for the underlying transaction",
)
async def retry_recovery(
    recovery_id: UUID,
    body: RetryRecoveryBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
    coordinator: CoordinatorDep,
) -> StartRecoveryChainResult:
    row = await session.get(RecoveryModel, recovery_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recovery not found"
        )

    handler = StartRecoveryChainHandler(session=session, coordinator=coordinator)
    return await handler.handle(
        StartRecoveryChainCommand(
            tenant_id=tenant_id,
            transaction_id=row.transaction_id,
            attempt_number=body.attempt_number,
        )
    )
