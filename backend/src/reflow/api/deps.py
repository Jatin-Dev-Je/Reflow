"""FastAPI dependency providers.

Single place for `Depends(...)` factories: settings, DB session, current tenant.
Routes never reach into globals — everything comes through here so tests can
override.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.config import Settings, get_settings
from reflow.core.database import session_scope
from reflow.core.observability.logging import bind_contextvars
from reflow.core.types import TenantId


async def get_settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# -----------------------------------------------------------------------------
# Tenant resolution
# -----------------------------------------------------------------------------
# In dev we accept `X-Tenant-Id` directly so the simulator can drive the
# system without going through auth.  In production the tenant comes from the
# JWT subject claim — that resolver replaces this function.
# -----------------------------------------------------------------------------

# Default demo tenant — matches the seed row in 001_initial_schema.sql.
_DEMO_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> TenantId:
    if x_tenant_id is None:
        tenant_id = TenantId(_DEMO_TENANT_ID)
    else:
        try:
            tenant_id = TenantId(UUID(x_tenant_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-Id must be a UUID",
            ) from exc
    bind_contextvars(tenant_id=str(tenant_id))
    return tenant_id


CurrentTenant = Annotated[TenantId, Depends(current_tenant)]
