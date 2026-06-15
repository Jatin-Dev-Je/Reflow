"""Dashboard endpoints.

These compute KPIs on demand from the read models. They MUST stay fast — the
queries are all bounded to a time window and use existing indexes. When we
need sub-second response under load, we'll move to pre-aggregated rollups
written by a worker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.dashboard.schemas import ExecutiveKpis, StatusBreakdown
from reflow.core.types import TenantId
from reflow.infrastructure.persistence.models import (
    RecoveryModel,
    TransactionModel,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90


async def _status_breakdown(
    session: AsyncSession, tenant_id: TenantId, start: datetime, end: datetime
) -> tuple[StatusBreakdown, int, int, int, int]:
    """Aggregate by status and return totals + counts the caller needs."""
    stmt = (
        select(TransactionModel.status, func.count().label("n"), func.sum(TransactionModel.amount_cents).label("amt"))
        .where(TransactionModel.tenant_id == tenant_id)
        .where(TransactionModel.created_at >= start)
        .where(TransactionModel.created_at < end)
        .group_by(TransactionModel.status)
    )
    rows = (await session.execute(stmt)).all()
    counts: dict[str, int] = {r.status: int(r.n) for r in rows}
    amounts: dict[str, int] = {r.status: int(r.amt or 0) for r in rows}

    breakdown = StatusBreakdown(
        pending=counts.get("pending", 0),
        succeeded=counts.get("succeeded", 0),
        failed=counts.get("failed", 0),
        recovering=counts.get("recovering", 0),
        recovered=counts.get("recovered", 0),
        abandoned=counts.get("abandoned", 0),
    )
    total = sum(counts.values())
    total_amount = sum(amounts.values())
    baseline_succeeded = counts.get("succeeded", 0)
    final_succeeded = baseline_succeeded + counts.get("recovered", 0)
    return breakdown, total, total_amount, baseline_succeeded, final_succeeded


async def _recovery_totals(
    session: AsyncSession, tenant_id: TenantId, start: datetime, end: datetime
) -> tuple[int, int, int]:
    """Return (attempted, succeeded, revenue_recovered_cents)."""
    stmt = (
        select(
            func.count().label("attempted"),
            func.count().filter(RecoveryModel.outcome == "recovered").label("succeeded"),
            func.coalesce(
                func.sum(RecoveryModel.recovered_amount_cents).filter(
                    RecoveryModel.outcome == "recovered"
                ),
                0,
            ).label("revenue"),
        )
        .where(RecoveryModel.tenant_id == tenant_id)
        .where(RecoveryModel.started_at >= start)
        .where(RecoveryModel.started_at < end)
    )
    row = (await session.execute(stmt)).one()
    return int(row.attempted or 0), int(row.succeeded or 0), int(row.revenue or 0)


@router.get(
    "/executive",
    response_model=ExecutiveKpis,
    summary="Executive KPI cards over a recent window",
)
async def get_executive_kpis(
    session: SessionDep,
    tenant_id: CurrentTenant,
    window_days: Annotated[int, Query(ge=1, le=MAX_WINDOW_DAYS)] = DEFAULT_WINDOW_DAYS,
) -> ExecutiveKpis:
    end = datetime.now(UTC)
    start = end - timedelta(days=window_days)

    breakdown, total, total_amount, baseline_succ, final_succ = await _status_breakdown(
        session, tenant_id, start, end
    )
    attempted, recovered, revenue_recovered = await _recovery_totals(
        session, tenant_id, start, end
    )

    baseline_rate = baseline_succ / total if total else 0.0
    reflow_rate = final_succ / total if total else 0.0
    recovery_rate = recovered / attempted if attempted else 0.0

    return ExecutiveKpis(
        window_start=start,
        window_end=end,
        currency="USD",
        total_transactions=total,
        total_amount_cents=total_amount,
        baseline_succeeded=baseline_succ,
        reflow_succeeded=final_succ,
        baseline_success_rate=baseline_rate,
        reflow_success_rate=reflow_rate,
        success_lift_pp=reflow_rate - baseline_rate,
        recoveries_attempted=attempted,
        recoveries_succeeded=recovered,
        recovery_rate=recovery_rate,
        revenue_recovered_cents=revenue_recovered,
        duplicate_charges=0,   # DB UNIQUE prevents — surfaced from audit when proven
        policy_violations=0,   # surfaced from policy.decisions when DB available
        status_breakdown=breakdown,
    )
