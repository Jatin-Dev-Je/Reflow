"""HTTP routes for the transactions context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from reflow.api.deps import CurrentTenant, SessionDep
from reflow.api.v1.transactions.schemas import (
    AttemptRead,
    TimelineEntry,
    TransactionRead,
    TransactionsPage,
    TransactionStats,
)
from reflow.domain.transactions import (
    CardFunding,
    CardMetadata,
    TransactionStatus,
)
from reflow.infrastructure.persistence.models import (
    AttemptModel,
    EventModel,
    TransactionModel,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200


def _to_card_metadata(row: TransactionModel) -> CardMetadata:
    return CardMetadata(
        bin=row.card_bin,
        last4=row.card_last4,
        brand=row.card_brand,
        funding=CardFunding(row.card_funding) if row.card_funding else CardFunding.UNKNOWN,
        country=row.card_country,
    )


def _to_transaction_read(row: TransactionModel) -> TransactionRead:
    return TransactionRead(
        id=row.id,
        tenant_id=row.tenant_id,
        external_id=row.external_id,
        customer_ref=row.customer_ref,
        amount_cents=row.amount_cents,
        currency=row.currency,
        card=_to_card_metadata(row),
        gateway_id=row.gateway_id,
        issuer_id=row.issuer_id,
        status=TransactionStatus(row.status),
        initial_failed_at=row.initial_failed_at,
        final_resolved_at=row.final_resolved_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "",
    response_model=TransactionsPage,
    summary="List transactions",
)
async def list_transactions(
    session: SessionDep,
    tenant_id: CurrentTenant,
    status_filter: Annotated[
        TransactionStatus | None,
        Query(alias="status", description="Filter by status."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> TransactionsPage:
    stmt = (
        select(TransactionModel)
        .where(TransactionModel.tenant_id == tenant_id)
        .order_by(desc(TransactionModel.created_at))
        .limit(limit + 1)  # fetch one extra to compute next_cursor flag
    )
    if status_filter is not None:
        stmt = stmt.where(TransactionModel.status == status_filter.value)

    rows = (await session.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    items = [_to_transaction_read(r) for r in rows[:limit]]
    return TransactionsPage(
        items=items,
        next_cursor=str(items[-1].created_at.isoformat()) if has_more and items else None,
    )


@router.get(
    "/stats",
    response_model=TransactionStats,
    summary="Aggregate transaction stats over a recent window",
)
async def transaction_stats(
    session: SessionDep,
    tenant_id: CurrentTenant,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> TransactionStats:
    end = datetime.now(UTC)
    start = end - timedelta(days=window_days)

    # Single grouped query — no N+1.
    stmt = (
        select(
            TransactionModel.status,
            TransactionModel.gateway_id,
            func.count().label("n"),
            func.sum(TransactionModel.amount_cents).label("amt"),
        )
        .where(TransactionModel.tenant_id == tenant_id)
        .where(TransactionModel.created_at >= start)
        .where(TransactionModel.created_at < end)
        .group_by(TransactionModel.status, TransactionModel.gateway_id)
    )
    rows = (await session.execute(stmt)).all()

    by_status: dict[str, int] = {}
    by_gateway: dict[str, int] = {}
    total = 0
    total_amount = 0
    for r in rows:
        n = int(r.n)
        by_status[r.status] = by_status.get(r.status, 0) + n
        by_gateway[r.gateway_id] = by_gateway.get(r.gateway_id, 0) + n
        total += n
        total_amount += int(r.amt or 0)

    avg = (total_amount // total) if total else 0
    return TransactionStats(
        window_days=window_days,
        total=total,
        total_amount_cents=total_amount,
        by_status=by_status,
        by_gateway=by_gateway,
        avg_amount_cents=avg,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionRead,
    summary="Get a single transaction",
)
async def get_transaction(
    transaction_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> TransactionRead:
    row = await session.get(TransactionModel, transaction_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )
    return _to_transaction_read(row)


@router.get(
    "/{transaction_id}/attempts",
    response_model=list[AttemptRead],
    summary="List charge attempts for a transaction",
)
async def list_attempts(
    transaction_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> list[AttemptRead]:
    txn = await session.get(TransactionModel, transaction_id)
    if txn is None or txn.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )

    stmt = (
        select(AttemptModel)
        .where(AttemptModel.transaction_id == transaction_id)
        .order_by(AttemptModel.attempt_number)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [AttemptRead.model_validate(r) for r in rows]


@router.get(
    "/{transaction_id}/timeline",
    response_model=list[TimelineEntry],
    summary="Trust View timeline — every event for this transaction in order",
)
async def transaction_timeline(
    transaction_id: UUID,
    session: SessionDep,
    tenant_id: CurrentTenant,
) -> list[TimelineEntry]:
    # Verify ownership first.
    txn = await session.get(TransactionModel, transaction_id)
    if txn is None or txn.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found"
        )

    stream_id = f"transaction-{transaction_id}"
    stmt = (
        select(EventModel)
        .where(EventModel.stream_id == stream_id)
        .order_by(EventModel.version)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        TimelineEntry(
            occurred_at=r.occurred_at,
            event_type=r.event_type,
            summary=_summary_for(r.event_type, r.payload),
            payload=r.payload,
        )
        for r in rows
    ]


def _summary_for(event_type: str, payload: dict) -> str:
    """One-line description per event type. Used for the Trust View timeline."""
    if event_type == "TransactionCreated":
        return f"Transaction created for {payload.get('amount_cents', 0) / 100:.2f} {payload.get('currency', '')}"
    if event_type == "AttemptRecorded":
        outcome = payload.get("outcome", "")
        return f"Charge attempt #{payload.get('attempt_number')} — {outcome}"
    if event_type == "PaymentFailed":
        decline = payload.get("decline", {}) or {}
        return f"Payment failed: {decline.get('code_normalized', 'unknown')}"
    if event_type == "PaymentRecovered":
        return f"Payment recovered ({payload.get('recovered_amount_cents', 0) / 100:.2f})"
    if event_type == "PaymentAbandoned":
        return f"Payment abandoned: {payload.get('reason', '')}"
    return event_type
