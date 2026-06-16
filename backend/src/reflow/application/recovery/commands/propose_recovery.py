"""Start a recovery and run the agent chain end-to-end.

This is the canonical 'one-button' command for the demo:
    1. Loads the failed transaction (must exist + be in 'failed' state).
    2. Builds a CoordinatorContext from the transaction + tenant settings +
       memory signals (pattern memory is best-effort; missing values OK).
    3. Creates a Recovery aggregate.
    4. Saves it (so the read model exists before the coordinator runs).
    5. Walks the Diagnosis -> Strategy -> Risk -> Policy -> Guard chain.
    6. Saves the recovery again with all chain events.

This handler is intentionally synchronous. The production saga driver runs
each step async via the worker; this command is what makes the chain
visible from the API for the demo.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.agents.orchestrator.coordinator import (
    CoordinatorContext,
    RecoveryCoordinator,
)
from reflow.application.recovery.dto import (
    RecoveryStepSummary,
    StartRecoveryChainCommand,
    StartRecoveryChainResult,
)
from reflow.core.exceptions import AggregateNotFoundError, InvariantViolationError
from reflow.core.observability.logging import get_logger
from reflow.core.types import TenantId
from reflow.domain.recovery import Recovery
from reflow.infrastructure.persistence.models import (
    AttemptModel,
    TransactionModel,
)
from reflow.infrastructure.persistence.projections.agent_outputs import (
    project_chain_outputs,
)
from reflow.infrastructure.persistence.repositories import SqlRecoveryRepository

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StartRecoveryChainHandler:
    session: AsyncSession
    coordinator: RecoveryCoordinator

    async def handle(self, cmd: StartRecoveryChainCommand) -> StartRecoveryChainResult:
        txn = await self._load_transaction(cmd.transaction_id, cmd.tenant_id)
        latest_attempt = await self._latest_attempt(cmd.transaction_id)

        recovery = Recovery.start(
            recovery_id=Recovery.new_id(),
            tenant_id=cmd.tenant_id,
            transaction_id=cmd.transaction_id,
            attempt_number=cmd.attempt_number,
        )
        repo = SqlRecoveryRepository(self.session)
        await repo.save(recovery)  # persist initial RecoveryCreated event + read-model row

        ctx = _build_context(
            txn=txn,
            latest_attempt=latest_attempt,
            attempt_number=cmd.attempt_number,
        )

        result = await self.coordinator.run_full(recovery=recovery, ctx=ctx)
        await repo.save(recovery)

        # Project agent outputs into read-model tables so the UI can list them.
        if result.produced and latest_attempt is not None:
            from reflow.core.types import AttemptId

            await project_chain_outputs(
                self.session,
                tenant_id=cmd.tenant_id,
                transaction_id=cmd.transaction_id,
                attempt_id=AttemptId(latest_attempt.id),
                recovery_id=recovery.id,
                produced=result.produced,
            )

        _logger.info(
            "recovery.chain.completed",
            recovery_id=str(recovery.id),
            transaction_id=str(cmd.transaction_id),
            final_state=result.final_state.value,
            stopped_reason=result.stopped_reason,
            step_count=len(result.steps),
        )

        return StartRecoveryChainResult(
            recovery_id=recovery.id,
            final_state=result.final_state.value,
            stopped_reason=result.stopped_reason,
            steps=[
                RecoveryStepSummary(
                    name=s.name,
                    artifact_id=s.artifact_id,
                    telemetry=s.telemetry,
                )
                for s in result.steps
            ],
        )

    async def _load_transaction(self, txn_id, tenant_id: TenantId) -> TransactionModel:
        row = await self.session.get(TransactionModel, txn_id)
        if row is None or row.tenant_id != tenant_id:
            raise AggregateNotFoundError(
                "Transaction not found",
                context={"transaction_id": str(txn_id)},
            )
        if row.status not in {"failed", "recovering"}:
            raise InvariantViolationError(
                f"Recovery can only start from a failed/recovering transaction "
                f"(current status={row.status!r})"
            )
        return row

    async def _latest_attempt(self, txn_id) -> AttemptModel | None:
        stmt = (
            select(AttemptModel)
            .where(AttemptModel.transaction_id == txn_id)
            .order_by(AttemptModel.attempt_number.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


def _build_context(
    *,
    txn: TransactionModel,
    latest_attempt: AttemptModel | None,
    attempt_number: int,
) -> CoordinatorContext:
    """Construct CoordinatorContext from persisted state.

    Pattern memory / health signals are stubbed to safe defaults for now —
    when the memory subsystem lands, they're populated from intel.* and
    health.* views in this same function.
    """
    decline_code = None
    decline_category_value = None
    decline_message = None
    if latest_attempt is not None:
        decline_code = latest_attempt.decline_code_normalized or latest_attempt.decline_code
        decline_category_value = latest_attempt.decline_category
        decline_message = latest_attempt.decline_message

    return CoordinatorContext(
        amount_cents=txn.amount_cents,
        currency=txn.currency,
        gateway_provider=txn.gateway_id,
        issuer_id=txn.issuer_id,
        card_bin=txn.card_bin,
        decline_code=decline_code,
        decline_category_value=decline_category_value,
        decline_message=decline_message,
        # Memory signals — best-effort defaults until intel.* is wired.
        gateway_recent_success_rate=None,
        issuer_recent_success_rate=None,
        similar_failures_last_24h=0,
        recent_recovery_success_rate=None,
        pattern_delayed_retry_success_rate=None,
        pattern_reroute_success_rate=None,
        pattern_payment_link_success_rate=None,
        pattern_avg_recovery_delay_seconds=None,
        historical_dup_charge_rate_for_strategy=None,
        alternate_gateways=(),
        tenant_max_retries=3,
        tenant_high_value_threshold_cents=5_000_000,
        tenant_hitl_required_above_cents=100_000_000,
        max_delay_seconds=86_400,
        attempt_number=attempt_number,
        previous_attempts_failed=max(
            0, (latest_attempt.attempt_number if latest_attempt else 0)
        ),
    )
