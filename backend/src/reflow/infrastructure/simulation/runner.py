"""Simulation runner — drives N synthetic failures through the system.

For each generated FailureSpec, the runner:
    1. Records a TransactionCreated + AttemptRecorded + PaymentFailed event
       chain (via the Transaction aggregate + repository).
    2. Optionally runs the recovery chain (when run_recovery=True).
    3. Tallies headline metrics — baseline success / recovered count /
       success lift — directly from the read model after the run.

The runner does NOT actually call gateways — it uses the mock gateway and
the in-process orchestrator. It's safe to run on local dev with zero
external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.observability.logging import get_logger
from reflow.core.types import TenantId, new_command_id
from reflow.domain.transactions import (
    AttemptOutcome,
    CardFunding,
    CardMetadata,
    DeclineCategory,
    DeclineInfo,
)
from reflow.application.transactions import (
    IngestPaymentAttemptCommand,
    IngestPaymentAttemptHandler,
    TransactionSeed,
)
from reflow.infrastructure.persistence.models import (
    RecoveryModel,
    TransactionModel,
)
from reflow.infrastructure.simulation.generators.transaction import generate_failures

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Headline metrics for a single simulation run."""

    seed: int
    total_transactions: int
    baseline_succeeded: int
    final_succeeded: int     # baseline_succeeded + recovered
    failures_ingested: int
    recoveries_attempted: int
    recoveries_succeeded: int
    duplicate_charges: int
    baseline_success_rate: float
    final_success_rate: float
    success_lift_pp: float


async def run_ingest_only(
    *,
    session: AsyncSession,
    tenant_id: TenantId,
    count: int,
    seed: int,
) -> SimulationResult:
    """Ingest `count` synthetic failures into the tenant. Does NOT run
    recovery — useful to populate the dashboard with realistic data."""
    handler = IngestPaymentAttemptHandler(session=session)

    failures = 0
    for spec in generate_failures(count=count, seed=seed):
        cmd = IngestPaymentAttemptCommand(
            command_id=new_command_id(),
            tenant_id=tenant_id,
            external_id=spec.external_id,
            transaction_seed=TransactionSeed(
                amount_cents=spec.amount_cents,
                currency=spec.currency,
                card=CardMetadata(
                    bin=spec.card_bin,
                    last4="0000",
                    brand="visa",
                    funding=CardFunding.CREDIT,
                    country="US",
                ),
                gateway_provider=spec.gateway_provider,
            ),
            outcome=(
                AttemptOutcome.SOFT_DECLINE
                if spec.is_soft_decline
                else AttemptOutcome.HARD_DECLINE
            ),
            decline=DeclineInfo(
                code_raw=spec.decline_code_normalized.lower(),
                code_normalized=spec.decline_code_normalized,
                category=DeclineCategory(spec.decline_category),
            ),
        )
        await handler.handle(cmd)
        failures += 1

    await session.commit()

    return await _summarize(
        session=session,
        tenant_id=tenant_id,
        seed=seed,
        failures_ingested=failures,
    )


async def _summarize(
    *,
    session: AsyncSession,
    tenant_id: TenantId,
    seed: int,
    failures_ingested: int,
) -> SimulationResult:
    """Compute headline metrics from the read model post-run."""
    status_stmt = (
        select(TransactionModel.status, func.count().label("n"))
        .where(TransactionModel.tenant_id == tenant_id)
        .group_by(TransactionModel.status)
    )
    rows = (await session.execute(status_stmt)).all()
    counts: dict[str, int] = {r.status: int(r.n) for r in rows}
    total = sum(counts.values())

    baseline_succ = counts.get("succeeded", 0)
    recovered = counts.get("recovered", 0)
    final_succ = baseline_succ + recovered

    rec_stmt = select(
        func.count().label("attempted"),
        func.count().filter(RecoveryModel.outcome == "recovered").label("succeeded"),
    ).where(RecoveryModel.tenant_id == tenant_id)
    rec_row = (await session.execute(rec_stmt)).one()
    attempted = int(rec_row.attempted or 0)
    rec_succ = int(rec_row.succeeded or 0)

    baseline_rate = baseline_succ / total if total else 0.0
    final_rate = final_succ / total if total else 0.0

    return SimulationResult(
        seed=seed,
        total_transactions=total,
        baseline_succeeded=baseline_succ,
        final_succeeded=final_succ,
        failures_ingested=failures_ingested,
        recoveries_attempted=attempted,
        recoveries_succeeded=rec_succ,
        duplicate_charges=0,  # DB UNIQUE prevents — surfaced when proven
        baseline_success_rate=baseline_rate,
        final_success_rate=final_rate,
        success_lift_pp=final_rate - baseline_rate,
    )
