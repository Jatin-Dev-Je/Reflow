"""Concrete RecoveryRepository.

Event-sourced — every state change goes through the event store first, then
projects to recovery.recoveries + recovery.steps for fast queries.

The state machine and invariants live in the Recovery aggregate; this class
just bridges the aggregate to persistence and updates the read model.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.types import RecoveryId
from reflow.domain.recovery import (
    Recovery,
    RecoveryApprovalRequested,
    RecoveryApproved,
    RecoveryCreated,
    RecoveryDiagnosed,
    RecoveryExecutionCompleted,
    RecoveryExecutionStarted,
    RecoveryFailed,
    RecoveryPolicyEvaluated,
    RecoveryRejected,
    RecoveryRiskAssessed,
    RecoveryStrategyProposed,
    RecoverySucceeded,
)
from reflow.infrastructure.persistence.models import (
    RecoveryModel,
    RecoveryStepModel,
)
from reflow.infrastructure.persistence.repositories.event_store_repository import (
    EventStoreRepository,
)


class SqlRecoveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventStoreRepository(session)

    # ---- Read --------------------------------------------------------------
    async def load(self, recovery_id: RecoveryId) -> Recovery | None:
        row = await self._session.execute(
            select(RecoveryModel.tenant_id).where(RecoveryModel.id == recovery_id)
        )
        tenant_id_row = row.scalar_one_or_none()
        if tenant_id_row is None:
            return None
        events = await self._events.materialize_stream(
            stream_id=f"recovery-{recovery_id}", tenant_id=tenant_id_row  # type: ignore[arg-type]
        )
        if not events:
            return None
        return Recovery.replay(events)

    # ---- Write -------------------------------------------------------------
    async def save(self, recovery: Recovery) -> None:
        pending = recovery.pull_pending_events()
        if not pending:
            return

        prior_state_before = await self._current_state(recovery.id)
        stored = await self._events.append_events(
            stream_id=f"recovery-{recovery.id}",
            expected_version=recovery.version,
            events=pending,
        )

        step_number = await self._next_step_number(recovery.id)
        last_state = prior_state_before or "created"

        for ev, persisted in zip(pending, stored, strict=True):
            await self._project(ev)
            new_state = recovery.state.value  # final state may have multiple events
            await self._record_step(
                recovery_id=recovery.id,
                step_number=step_number,
                from_state=last_state,
                to_state=new_state,
                triggered_by="domain",
                input={"event_type": type(ev).__name__, "version": persisted.version},
                output=None,
            )
            step_number += 1
            last_state = new_state

        recovery.version += len(pending)

    async def _current_state(self, recovery_id: RecoveryId) -> str | None:
        stmt = select(RecoveryModel.state).where(RecoveryModel.id == recovery_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _next_step_number(self, recovery_id: RecoveryId) -> int:
        from sqlalchemy import func

        stmt = select(func.coalesce(func.max(RecoveryStepModel.step_number), 0)).where(
            RecoveryStepModel.recovery_id == recovery_id
        )
        return ((await self._session.execute(stmt)).scalar() or 0) + 1

    async def _record_step(
        self,
        *,
        recovery_id: RecoveryId,
        step_number: int,
        from_state: str,
        to_state: str,
        triggered_by: str,
        input: dict | None,
        output: dict | None,
    ) -> None:
        now = datetime.now(UTC)
        self._session.add(
            RecoveryStepModel(
                recovery_id=recovery_id,
                step_number=step_number,
                from_state=from_state,
                to_state=to_state,
                triggered_by=triggered_by,
                handler=None,
                input=input,
                output=output,
                started_at=now,
                completed_at=now,
                duration_ms=0,
            )
        )

    # ---- Projections -------------------------------------------------------
    async def _project(self, event: object) -> None:
        match event:
            case RecoveryCreated() as ev:
                stmt = pg_insert(RecoveryModel).values(
                    id=ev.recovery_id,
                    tenant_id=ev.tenant_id,
                    transaction_id=ev.transaction_id,
                    state="created",
                    recovery_key=ev.recovery_key,
                    started_at=ev.occurred_at,
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=[RecoveryModel.id])
                await self._session.execute(stmt)

            case RecoveryDiagnosed() as ev:
                await self._patch(
                    ev.recovery_id, state="diagnosed", diagnosis_id=ev.diagnosis_id
                )
            case RecoveryStrategyProposed() as ev:
                await self._patch(
                    ev.recovery_id, state="strategy_proposed", strategy_id=ev.strategy_id
                )
            case RecoveryRiskAssessed() as ev:
                await self._patch(
                    ev.recovery_id,
                    state="risk_assessed",
                    risk_assessment_id=ev.risk_assessment_id,
                )
            case RecoveryPolicyEvaluated() as ev:
                await self._patch(
                    ev.recovery_id,
                    state="policy_evaluated",
                    policy_decision_id=ev.policy_decision_id,
                )
            case RecoveryApprovalRequested() as ev:
                await self._patch(ev.recovery_id, state="awaiting_approval")
            case RecoveryApproved() as ev:
                await self._patch(ev.recovery_id, state="approved")
            case RecoveryRejected() as ev:
                await self._patch(
                    ev.recovery_id,
                    state="failed",
                    last_error=ev.rejection_reason,
                    completed_at=ev.occurred_at,
                    outcome="failed",
                )
            case RecoveryExecutionStarted() as ev:
                await self._patch(ev.recovery_id, state="executing")
            case RecoveryExecutionCompleted() as ev:
                # success -> executed, anything else -> failed
                next_state = "executed" if ev.outcome.value == "success" else "failed"
                values: dict = {"state": next_state}
                if next_state == "failed":
                    values["completed_at"] = ev.occurred_at
                    values["outcome"] = "failed"
                await self._patch(ev.recovery_id, **values)
            case RecoverySucceeded() as ev:
                await self._patch(
                    ev.recovery_id,
                    state="recovered",
                    outcome="recovered",
                    recovered_amount_cents=ev.recovered_amount_cents,
                    completed_at=ev.occurred_at,
                )
            case RecoveryFailed() as ev:
                await self._patch(
                    ev.recovery_id,
                    state="failed",
                    last_error=ev.reason,
                    outcome="failed",
                    completed_at=ev.occurred_at,
                )

    async def _patch(self, recovery_id: RecoveryId, **values: object) -> None:
        values["version"] = RecoveryModel.version + 1  # type: ignore[assignment]
        await self._session.execute(
            update(RecoveryModel).where(RecoveryModel.id == recovery_id).values(**values)
        )
