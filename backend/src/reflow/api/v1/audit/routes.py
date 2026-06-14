"""Audit endpoints — events, streams, anchors, verify."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.audit.schemas import (
    AuditEventRead,
    ChainAnchorRead,
    VerifyResponse,
)
from reflow.core.exceptions import DomainError
from reflow.core.types import EventId
from reflow.infrastructure.audit_log import AuditVerifier
from reflow.infrastructure.persistence.repositories import AuditRepository

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/events",
    response_model=list[AuditEventRead],
    summary="List recent audit events",
)
async def list_events(
    session: SessionDep,
    tenant_id: CurrentTenant,
    stream_type: Annotated[
        str | None, Query(description="Filter by stream type (e.g. 'transaction').")
    ] = None,
    event_type: Annotated[
        str | None, Query(description="Filter by event type (e.g. 'PaymentFailed').")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[AuditEventRead]:
    repo = AuditRepository(session)
    events = await repo.list_events(
        tenant_id=tenant_id,
        stream_type=stream_type,
        event_type=event_type,
        limit=limit,
    )
    return [AuditEventRead.model_validate(e) for e in events]


@router.get(
    "/events/{event_id}",
    response_model=AuditEventRead,
    summary="Get a single audit event",
)
async def get_event(
    event_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> AuditEventRead:
    repo = AuditRepository(session)
    event = await repo.get_event(tenant_id=tenant_id, event_id=EventId(event_id))
    return AuditEventRead.model_validate(event)


@router.get(
    "/streams/{stream_id}",
    response_model=list[AuditEventRead],
    summary="List all events for an aggregate stream in order",
)
async def get_stream(
    stream_id: str,
    session: SessionDep,
    tenant_id: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[AuditEventRead]:
    repo = AuditRepository(session)
    events = await repo.list_stream_events(
        tenant_id=tenant_id, stream_id=stream_id, limit=limit
    )
    return [AuditEventRead.model_validate(e) for e in events]


@router.get(
    "/anchors",
    response_model=list[ChainAnchorRead],
    summary="List signed Merkle anchors",
)
async def list_anchors(
    session: SessionDep,
    _tenant_id: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[ChainAnchorRead]:
    repo = AuditRepository(session)
    anchors = await repo.list_anchors(limit=limit)
    return [ChainAnchorRead.model_validate(a) for a in anchors]


@router.get(
    "/anchors/latest",
    response_model=ChainAnchorRead | None,
    summary="Get the most recently signed anchor",
)
async def latest_anchor(
    session: SessionDep,
    _tenant_id: CurrentTenant,
) -> ChainAnchorRead | None:
    repo = AuditRepository(session)
    anchor = await repo.latest_anchor()
    return ChainAnchorRead.model_validate(anchor) if anchor else None


@router.get(
    "/verify/{event_id}",
    response_model=VerifyResponse,
    summary="Cryptographic proof of event inclusion in a signed anchor",
)
async def verify_event(
    event_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> VerifyResponse:
    """Returns a Merkle inclusion proof for `event_id` plus a verification result.

    Clients can re-run verification offline using `proof` and the public key
    from `GET /system/audit-key` (TODO). The server runs it too, so the
    `valid` flag is a fast-path indicator for dashboards.
    """
    # Tenant ownership check — fail before doing any chain work.
    repo = AuditRepository(session)
    await repo.get_event(tenant_id=tenant_id, event_id=EventId(event_id))

    verifier = AuditVerifier(session)
    try:
        proof = await verifier.build_proof(EventId(event_id))
    except DomainError:
        # Re-raise so install_error_handlers produces the right HTTP status.
        raise

    result = AuditVerifier.verify_proof(proof)
    return VerifyResponse(
        valid=result.valid,
        reason=result.reason,
        proof=proof.model_dump(mode="json"),
    )
