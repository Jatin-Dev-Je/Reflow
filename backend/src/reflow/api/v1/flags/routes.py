"""Feature flag + kill switch endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.flags.schemas import (
    ActivateKillSwitchBody,
    EffectiveFlag,
    KillSwitchRead,
    SetTenantFlagBody,
    TenantFlagResult,
)
from reflow.core.observability.logging import get_logger
from reflow.core.types import TenantId
from reflow.infrastructure.persistence.models import (
    FeatureFlagModel,
    KillSwitchModel,
    TenantFlagModel,
)

router = APIRouter(prefix="/flags", tags=["flags"])
_logger = get_logger(__name__)


# ----------------------------------------------------------- Feature flags ----


async def _resolve_flag(
    session, *, key: str, tenant_id: TenantId
) -> EffectiveFlag | None:
    flag = await session.get(FeatureFlagModel, key)
    if flag is None:
        return None
    override = await session.execute(
        select(TenantFlagModel)
        .where(TenantFlagModel.tenant_id == tenant_id)
        .where(TenantFlagModel.key == key)
    )
    tenant_row = override.scalar_one_or_none()

    resolved: Any = (
        tenant_row.value if tenant_row is not None else flag.default_value
    )

    return EffectiveFlag(
        key=flag.key,
        description=flag.description,
        flag_type=flag.flag_type,
        default_value=flag.default_value,
        tenant_override=tenant_row.value if tenant_row else None,
        rollout_percent=tenant_row.rollout_percent if tenant_row else None,
        resolved_value=resolved,
    )


@router.get(
    "",
    response_model=list[EffectiveFlag],
    summary="List all flags with their effective value for the current tenant",
)
async def list_flags(
    session: SessionDep, tenant_id: CurrentTenant
) -> list[EffectiveFlag]:
    flags = (await session.execute(select(FeatureFlagModel))).scalars().all()
    out: list[EffectiveFlag] = []
    for f in flags:
        eff = await _resolve_flag(session, key=f.key, tenant_id=tenant_id)
        if eff is not None:
            out.append(eff)
    return out


@router.put(
    "/{key}",
    response_model=TenantFlagResult,
    summary="Set or update the tenant override for a flag",
)
async def set_tenant_flag(
    key: str,
    body: SetTenantFlagBody,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> TenantFlagResult:
    flag = await session.get(FeatureFlagModel, key)
    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown flag"
        )

    stmt = (
        pg_insert(TenantFlagModel)
        .values(
            tenant_id=tenant_id,
            key=key,
            value=body.value,
            rollout_percent=body.rollout_percent,
        )
        .on_conflict_do_update(
            index_elements=[TenantFlagModel.tenant_id, TenantFlagModel.key],
            set_={
                "value": body.value,
                "rollout_percent": body.rollout_percent,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    _logger.info(
        "flags.tenant_override.set",
        tenant_id=str(tenant_id),
        key=key,
        rollout_percent=body.rollout_percent,
    )

    row = (
        await session.execute(
            select(TenantFlagModel)
            .where(TenantFlagModel.tenant_id == tenant_id)
            .where(TenantFlagModel.key == key)
        )
    ).scalar_one()
    return TenantFlagResult(
        tenant_id=row.tenant_id,
        key=row.key,
        value=row.value,
        rollout_percent=row.rollout_percent,
        updated_at=row.updated_at,
    )


# ----------------------------------------------------------- Kill switches ----


@router.get(
    "/kill-switches",
    response_model=list[KillSwitchRead],
    summary="List all kill switches",
)
async def list_kill_switches(
    session: SessionDep, _tenant_id: CurrentTenant
) -> list[KillSwitchRead]:
    rows = (await session.execute(select(KillSwitchModel))).scalars().all()
    return [KillSwitchRead.model_validate(r) for r in rows]


@router.post(
    "/kill-switches/{key}/activate",
    response_model=KillSwitchRead,
    summary="Activate a kill switch — STOP",
)
async def activate_kill_switch(
    key: str,
    body: ActivateKillSwitchBody,
    session: SessionDep,
    _tenant_id: CurrentTenant,
) -> KillSwitchRead:
    row = await session.get(KillSwitchModel, key)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown kill switch"
        )
    row.is_active = True
    row.activated_at = datetime.now(UTC)
    row.reason = body.reason
    row.updated_at = datetime.now(UTC)
    await session.commit()
    _logger.warning("kill_switch.activated", key=key, reason=body.reason)
    return KillSwitchRead.model_validate(row)


@router.post(
    "/kill-switches/{key}/deactivate",
    response_model=KillSwitchRead,
    summary="Deactivate a kill switch — resume",
)
async def deactivate_kill_switch(
    key: str,
    session: SessionDep,
    _tenant_id: CurrentTenant,
) -> KillSwitchRead:
    row = await session.get(KillSwitchModel, key)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown kill switch"
        )
    row.is_active = False
    row.activated_at = None
    row.reason = None
    row.updated_at = datetime.now(UTC)
    await session.commit()
    _logger.info("kill_switch.deactivated", key=key)
    return KillSwitchRead.model_validate(row)
