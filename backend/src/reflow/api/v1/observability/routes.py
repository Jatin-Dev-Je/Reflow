"""Observability endpoints — list agent runs, LLM calls, cost breakdowns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.observability.schemas import (
    AgentRunRead,
    CostBreakdown,
    CostBreakdownEntry,
    LlmCallRead,
)
from reflow.infrastructure.persistence.models import (
    AgentRunModel,
    LlmCallModel,
)

router = APIRouter(prefix="/observability", tags=["observability"])

PAGE_DEFAULT = 50
PAGE_MAX = 200


# -------------------------------------------------------------- Agent runs ----


@router.get(
    "/agent-runs",
    response_model=list[AgentRunRead],
    summary="List recent agent runs (Diagnosis, Strategy, Risk, Guard)",
)
async def list_agent_runs(
    session: SessionDep,
    tenant_id: CurrentTenant,
    agent_name: Annotated[
        str | None, Query(description="Filter by agent — diagnosis/strategy/risk/guard")
    ] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[AgentRunRead]:
    stmt = (
        select(AgentRunModel)
        .where(AgentRunModel.tenant_id == tenant_id)
        .order_by(desc(AgentRunModel.started_at))
        .limit(limit)
    )
    if agent_name is not None:
        stmt = stmt.where(AgentRunModel.agent_name == agent_name)
    if status_filter is not None:
        stmt = stmt.where(AgentRunModel.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [AgentRunRead.model_validate(r) for r in rows]


@router.get(
    "/agent-runs/{run_id}",
    response_model=AgentRunRead,
    summary="Get a single agent run",
)
async def get_agent_run(
    run_id: UUID, session: SessionDep, tenant_id: CurrentTenant
) -> AgentRunRead:
    row = await session.get(AgentRunModel, run_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found"
        )
    return AgentRunRead.model_validate(row)


# -------------------------------------------------------------- LLM calls -----


@router.get(
    "/llm-calls",
    response_model=list[LlmCallRead],
    summary="List recent LLM calls",
)
async def list_llm_calls(
    session: SessionDep,
    tenant_id: CurrentTenant,
    provider: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[LlmCallRead]:
    # Tenant scope: only runs we own, joined to llm_calls.
    stmt = (
        select(LlmCallModel)
        .join(AgentRunModel, AgentRunModel.id == LlmCallModel.agent_run_id)
        .where(AgentRunModel.tenant_id == tenant_id)
        .order_by(desc(LlmCallModel.called_at))
        .limit(limit)
    )
    if provider is not None:
        stmt = stmt.where(LlmCallModel.provider == provider)
    rows = (await session.execute(stmt)).scalars().all()
    return [LlmCallRead.model_validate(r) for r in rows]


@router.get(
    "/llm-calls/{call_id}",
    response_model=LlmCallRead,
    summary="Get a single LLM call",
)
async def get_llm_call(
    call_id: UUID, session: SessionDep, tenant_id: CurrentTenant
) -> LlmCallRead:
    row = (
        await session.execute(
            select(LlmCallModel)
            .join(AgentRunModel, AgentRunModel.id == LlmCallModel.agent_run_id)
            .where(LlmCallModel.id == call_id)
            .where(AgentRunModel.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="LLM call not found"
        )
    return LlmCallRead.model_validate(row)


# -------------------------------------------------------------- Costs ---------


@router.get(
    "/costs",
    response_model=CostBreakdown,
    summary="Cost breakdown by agent + by provider over a window",
)
async def cost_breakdown(
    session: SessionDep,
    tenant_id: CurrentTenant,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> CostBreakdown:
    end = datetime.now(UTC)
    start = end - timedelta(days=window_days)

    # By agent (from obs.agent_runs).
    by_agent_rows = (
        await session.execute(
            select(
                AgentRunModel.agent_name,
                func.count().label("runs"),
                func.coalesce(func.sum(AgentRunModel.total_cost_usd), 0).label("cost"),
                func.coalesce(func.sum(AgentRunModel.total_tokens_in), 0).label("tin"),
                func.coalesce(func.sum(AgentRunModel.total_tokens_out), 0).label("tout"),
                func.coalesce(func.avg(AgentRunModel.latency_ms), None).label("lat"),
            )
            .where(AgentRunModel.tenant_id == tenant_id)
            .where(AgentRunModel.started_at >= start)
            .where(AgentRunModel.started_at < end)
            .group_by(AgentRunModel.agent_name)
        )
    ).all()

    # By provider (from obs.llm_calls joined to runs for tenant scoping).
    by_provider_rows = (
        await session.execute(
            select(
                LlmCallModel.provider,
                func.count().label("runs"),
                func.coalesce(func.sum(LlmCallModel.cost_usd), 0).label("cost"),
                func.coalesce(func.sum(LlmCallModel.tokens_in), 0).label("tin"),
                func.coalesce(func.sum(LlmCallModel.tokens_out), 0).label("tout"),
                func.coalesce(func.avg(LlmCallModel.latency_ms), None).label("lat"),
            )
            .join(AgentRunModel, AgentRunModel.id == LlmCallModel.agent_run_id)
            .where(AgentRunModel.tenant_id == tenant_id)
            .where(LlmCallModel.called_at >= start)
            .where(LlmCallModel.called_at < end)
            .group_by(LlmCallModel.provider)
        )
    ).all()

    by_agent = [
        CostBreakdownEntry(
            dimension_value=r.agent_name,
            runs=int(r.runs),
            total_cost_usd=float(r.cost or 0),
            total_tokens_in=int(r.tin or 0),
            total_tokens_out=int(r.tout or 0),
            avg_latency_ms=int(r.lat) if r.lat is not None else None,
        )
        for r in by_agent_rows
    ]
    by_provider = [
        CostBreakdownEntry(
            dimension_value=r.provider,
            runs=int(r.runs),
            total_cost_usd=float(r.cost or 0),
            total_tokens_in=int(r.tin or 0),
            total_tokens_out=int(r.tout or 0),
            avg_latency_ms=int(r.lat) if r.lat is not None else None,
        )
        for r in by_provider_rows
    ]

    grand_total = sum(e.total_cost_usd for e in by_agent)
    grand_runs = sum(e.runs for e in by_agent)

    return CostBreakdown(
        window_days=window_days,
        grand_total_usd=grand_total,
        grand_total_runs=grand_runs,
        by_agent=by_agent,
        by_provider=by_provider,
    )
