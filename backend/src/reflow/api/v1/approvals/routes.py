"""Approval queue endpoints — HITL workflow.

Lists recoveries stuck at `awaiting_approval` and lets an authorised user
approve or reject. Both operations go through the Recovery aggregate so the
state machine + event audit trail are preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, select

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.approvals.schemas import (
    ApprovalDecisionResult,
    ApproveBody,
    PendingApproval,
    RejectBody,
)
from reflow.core.events.event import EventMetadata
from reflow.core.observability.logging import get_logger
from reflow.core.types import RecoveryId
from reflow.domain.recovery import RecoveryState
from reflow.infrastructure.persistence.models import RecoveryModel
from reflow.infrastructure.persistence.repositories import SqlRecoveryRepository

router = APIRouter(prefix="/approvals", tags=["approvals"])

_logger = get_logger(__name__)
PAGE_DEFAULT = 50
PAGE_MAX = 200


@router.get(
    "",
    response_model=list[PendingApproval],
    summary="List pending approvals",
)
async def list_pending(
    session: SessionDep,
    tenant_id: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=PAGE_MAX)] = PAGE_DEFAULT,
) -> list[PendingApproval]:
    stmt = (
        select(RecoveryModel)
        .where(RecoveryModel.tenant_id == tenant_id)
        .where(RecoveryModel.state == RecoveryState.AWAITING_APPROVAL.value)
        .order_by(desc(RecoveryModel.started_at))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        PendingApproval(
            recovery_id=r.id,
            tenant_id=r.tenant_id,
            transaction_id=r.transaction_id,
            policy_decision_id=r.policy_decision_id,
            reason=r.last_error,  # reused as the proximate reason for approval
            started_at=r.started_at,
        )
        for r in rows
    ]


@router.get(
    "/{recovery_id}",
    response_model=PendingApproval,
    summary="Get a single pending approval",
)
async def get_pending(
    recovery_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> PendingApproval:
    row = await session.get(RecoveryModel, recovery_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found"
        )
    if row.state != RecoveryState.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recovery is in state {row.state!r}, not awaiting_approval",
        )
    return PendingApproval(
        recovery_id=row.id,
        tenant_id=row.tenant_id,
        transaction_id=row.transaction_id,
        policy_decision_id=row.policy_decision_id,
        reason=row.last_error,
        started_at=row.started_at,
    )


@router.post(
    "/{recovery_id}/approve",
    response_model=ApprovalDecisionResult,
    summary="Approve a pending recovery (HITL)",
)
async def approve(
    recovery_id: UUID,
    body: ApproveBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> ApprovalDecisionResult:
    repo = SqlRecoveryRepository(session)
    recovery = await repo.load(RecoveryId(recovery_id))
    if recovery is None or recovery.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recovery not found"
        )
    recovery.approve(
        approver_id=None,  # TODO: wire to JWT subject when auth is in place
        note=body.note,
        metadata=EventMetadata(source="api:approvals.approve"),
    )
    await repo.save(recovery)
    _logger.info(
        "approvals.approved",
        recovery_id=str(recovery.id),
        tenant_id=str(tenant_id),
    )
    return ApprovalDecisionResult(
        recovery_id=recovery.id,
        new_state=recovery.state.value,
        decided_at=datetime.now(UTC),
    )


@router.post(
    "/{recovery_id}/reject",
    response_model=ApprovalDecisionResult,
    summary="Reject a pending recovery (HITL)",
)
async def reject(
    recovery_id: UUID,
    body: RejectBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> ApprovalDecisionResult:
    repo = SqlRecoveryRepository(session)
    recovery = await repo.load(RecoveryId(recovery_id))
    if recovery is None or recovery.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recovery not found"
        )
    recovery.reject(
        rejector_id=None,
        rejection_reason=body.reason,
        metadata=EventMetadata(source="api:approvals.reject"),
    )
    await repo.save(recovery)
    _logger.info(
        "approvals.rejected",
        recovery_id=str(recovery.id),
        tenant_id=str(tenant_id),
        reason=body.reason,
    )
    return ApprovalDecisionResult(
        recovery_id=recovery.id,
        new_state=recovery.state.value,
        decided_at=datetime.now(UTC),
    )
