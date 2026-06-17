"""Policy CRUD + version management + simulation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import desc, func, select

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.policies.schemas import (
    CreatePolicyBody,
    CreateVersionBody,
    PolicyRead,
    PolicyVersionRead,
    SimulateVersionBody,
    SimulateVersionResult,
    UpdatePolicyBody,
)
from reflow.core.observability.logging import get_logger
from reflow.core.security.signing import canonical_json, sha256_hex
from reflow.infrastructure.persistence.models import (
    PolicyDecisionModel,
    PolicyModel,
    PolicyVersionModel,
)

router = APIRouter(prefix="/policies", tags=["policies"])
_logger = get_logger(__name__)

ALLOWED_STATUS = {"draft", "active", "retired"}


# -------------------------------------------------------------- Policies ------


@router.get(
    "",
    response_model=list[PolicyRead],
    summary="List policies (tenant + global)",
)
async def list_policies(
    session: SessionDep, tenant_id: CurrentTenant
) -> list[PolicyRead]:
    stmt = (
        select(PolicyModel)
        .where(
            (PolicyModel.tenant_id == tenant_id) | (PolicyModel.tenant_id.is_(None))
        )
        .order_by(desc(PolicyModel.created_at))
        .limit(200)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [PolicyRead.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=PolicyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new policy (status starts as 'draft')",
)
async def create_policy(
    body: CreatePolicyBody, session: SessionDep, tenant_id: CurrentTenant
) -> PolicyRead:
    existing = await session.execute(
        select(PolicyModel)
        .where(PolicyModel.tenant_id == tenant_id)
        .where(PolicyModel.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy with that name already exists for this tenant",
        )

    policy = PolicyModel(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        status="draft",
    )
    session.add(policy)
    await session.commit()
    return PolicyRead.model_validate(policy)


@router.get(
    "/{policy_id}",
    response_model=PolicyRead,
    summary="Get a single policy",
)
async def get_policy(
    policy_id: UUID, session: SessionDep, tenant_id: CurrentTenant
) -> PolicyRead:
    row = await session.get(PolicyModel, policy_id)
    if row is None or (row.tenant_id is not None and row.tenant_id != tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    return PolicyRead.model_validate(row)


@router.patch(
    "/{policy_id}",
    response_model=PolicyRead,
    summary="Update a policy's description or status",
)
async def update_policy(
    policy_id: UUID,
    body: UpdatePolicyBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> PolicyRead:
    row = await session.get(PolicyModel, policy_id)
    if row is None or (row.tenant_id is not None and row.tenant_id != tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    if body.status is not None and body.status not in ALLOWED_STATUS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(ALLOWED_STATUS)}",
        )
    if body.description is not None:
        row.description = body.description
    if body.status is not None:
        row.status = body.status
    row.updated_at = datetime.now(UTC)
    await session.commit()
    return PolicyRead.model_validate(row)


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retire a policy (soft delete via status='retired')",
)
async def delete_policy(
    policy_id: UUID, session: SessionDep, tenant_id: CurrentTenant
) -> None:
    row = await session.get(PolicyModel, policy_id)
    if row is None or (row.tenant_id is not None and row.tenant_id != tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    row.status = "retired"
    row.updated_at = datetime.now(UTC)
    await session.commit()


# -------------------------------------------------------------- Versions ------


@router.get(
    "/{policy_id}/versions",
    response_model=list[PolicyVersionRead],
    summary="List version history of a policy",
)
async def list_versions(
    policy_id: UUID, session: SessionDep, tenant_id: CurrentTenant
) -> list[PolicyVersionRead]:
    policy = await session.get(PolicyModel, policy_id)
    if policy is None or (
        policy.tenant_id is not None and policy.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )
    rows = (
        await session.execute(
            select(PolicyVersionModel)
            .where(PolicyVersionModel.policy_id == policy_id)
            .order_by(desc(PolicyVersionModel.version))
        )
    ).scalars().all()
    return [PolicyVersionRead.model_validate(r) for r in rows]


@router.post(
    "/{policy_id}/versions",
    response_model=PolicyVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft version of a policy",
)
async def create_version(
    policy_id: UUID,
    body: CreateVersionBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> PolicyVersionRead:
    policy = await session.get(PolicyModel, policy_id)
    if policy is None or (
        policy.tenant_id is not None and policy.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    current_max = (
        await session.execute(
            select(func.coalesce(func.max(PolicyVersionModel.version), 0))
            .where(PolicyVersionModel.policy_id == policy_id)
        )
    ).scalar() or 0
    new_version_number = int(current_max) + 1

    rules_hash = sha256_hex(canonical_json(body.rules))

    version_row = PolicyVersionModel(
        policy_id=policy_id,
        version=new_version_number,
        rules=body.rules,
        rules_hash=rules_hash,
        notes=body.notes,
    )
    session.add(version_row)
    await session.commit()
    return PolicyVersionRead.model_validate(version_row)


@router.post(
    "/{policy_id}/versions/{version_id}/activate",
    response_model=PolicyVersionRead,
    summary="Activate a version — becomes the current policy",
)
async def activate_version(
    policy_id: UUID,
    version_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> PolicyVersionRead:
    policy = await session.get(PolicyModel, policy_id)
    if policy is None or (
        policy.tenant_id is not None and policy.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
        )

    version_row = await session.get(PolicyVersionModel, version_id)
    if version_row is None or version_row.policy_id != policy_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )

    prev = (
        await session.execute(
            select(PolicyVersionModel)
            .where(PolicyVersionModel.policy_id == policy_id)
            .where(PolicyVersionModel.activated_at.is_not(None))
            .where(PolicyVersionModel.deactivated_at.is_(None))
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for p in prev:
        if p.id != version_id:
            p.deactivated_at = now

    version_row.activated_at = now
    version_row.deactivated_at = None
    policy.current_version_id = version_id
    policy.status = "active"
    policy.updated_at = now
    await session.commit()
    _logger.info(
        "policy.version.activated",
        policy_id=str(policy_id),
        version_id=str(version_id),
        version=version_row.version,
    )
    return PolicyVersionRead.model_validate(version_row)


@router.post(
    "/{policy_id}/versions/{version_id}/simulate",
    response_model=SimulateVersionResult,
    summary="Count historical decisions that exist in a window (stubbed diff)",
)
async def simulate_version(
    policy_id: UUID,
    version_id: UUID,
    body: SimulateVersionBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> SimulateVersionResult:
    """Simulation harness — counts decisions in the window.

    Full per-decision diff (re-running each context_snapshot through the
    candidate rule set) is wired when the rule-DSL evaluator lands. For
    now this confirms the endpoint shape so the editor UI can be built.
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=body.window_days)

    decisions_count = (
        await session.execute(
            select(func.count())
            .select_from(PolicyDecisionModel)
            .where(PolicyDecisionModel.tenant_id == tenant_id)
            .where(PolicyDecisionModel.decided_at >= start)
            .where(PolicyDecisionModel.decided_at < end)
        )
    ).scalar() or 0

    breakdown = {
        "allow_to_deny": 0,
        "allow_to_require_approval": 0,
        "deny_to_allow": 0,
        "require_approval_to_allow": 0,
    }

    return SimulateVersionResult(
        window_days=body.window_days,
        decisions_evaluated=int(decisions_count),
        decisions_changed=0,
        change_breakdown=breakdown,
    )
