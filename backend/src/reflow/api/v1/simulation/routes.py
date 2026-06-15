"""Simulation endpoints — drive synthetic failures through the system.

These are demo-grade endpoints. For real benchmark runs at 100K+, the work
should move to a background ARQ worker so the HTTP request doesn't hold a
connection for minutes.
"""

from __future__ import annotations

from fastapi import APIRouter

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.simulation.schemas import (
    RunIngestBody,
    SimulationResultRead,
)
from reflow.infrastructure.simulation.runner import run_ingest_only

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post(
    "/ingest",
    response_model=SimulationResultRead,
    summary="Ingest N synthetic failed transactions (seeded, reproducible)",
)
async def ingest_synthetic(
    body: RunIngestBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> SimulationResultRead:
    result = await run_ingest_only(
        session=session,
        tenant_id=tenant_id,
        count=body.count,
        seed=body.seed,
    )
    return SimulationResultRead(
        seed=result.seed,
        total_transactions=result.total_transactions,
        baseline_succeeded=result.baseline_succeeded,
        final_succeeded=result.final_succeeded,
        failures_ingested=result.failures_ingested,
        recoveries_attempted=result.recoveries_attempted,
        recoveries_succeeded=result.recoveries_succeeded,
        duplicate_charges=result.duplicate_charges,
        baseline_success_rate=result.baseline_success_rate,
        final_success_rate=result.final_success_rate,
        success_lift_pp=result.success_lift_pp,
    )
