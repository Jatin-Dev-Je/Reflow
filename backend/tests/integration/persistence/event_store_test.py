"""EventStoreRepository integration tests.

Verifies against a real Postgres that:
    * append + load round-trip preserves event order and payload
    * Hash chain links events: event[N+1].previous_hash == event[N].event_hash
    * Optimistic concurrency: writing at wrong expected_version raises
    * Outbox rows are written in the same transaction
    * Snapshots persist and load by latest version
    * materialize_stream() reconstructs typed DomainEvents from rows
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.exceptions import ConcurrencyConflictError
from reflow.core.types import new_tenant_id, new_transaction_id
from reflow.domain.transactions import (
    AttemptOutcome,
    CardFunding,
    CardMetadata,
    DeclineCategory,
    DeclineInfo,
    Transaction,
)
from reflow.infrastructure.persistence import (
    EventStoreRepository,
    OutboxModel,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _txn_with_attempt() -> Transaction:
    txn = Transaction.create(
        transaction_id=new_transaction_id(),
        tenant_id=new_tenant_id(),
        external_id="ext_int_test",
        amount_cents=10_00,
        currency="USD",
        card=CardMetadata(
            bin="424242", last4="4242", brand="visa", funding=CardFunding.CREDIT, country="US"
        ),
        gateway_provider="stripe",
    )
    txn.record_attempt(
        outcome=AttemptOutcome.SOFT_DECLINE,
        decline=DeclineInfo(
            code_raw="insufficient_funds",
            code_normalized="FUNDS_INSUFFICIENT",
            category=DeclineCategory.FUNDS,
        ),
    )
    return txn


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


async def test_append_and_load_roundtrip(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)

    stored = await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=txn.pull_pending_events(),
    )
    await clean_event_store.commit()

    assert len(stored) == 3  # Created + AttemptRecorded + PaymentFailed
    assert [e.version for e in stored] == [1, 2, 3]
    assert [e.event_type for e in stored] == [
        "TransactionCreated",
        "AttemptRecorded",
        "PaymentFailed",
    ]

    loaded = await repo.load_stream(stream_id=f"transaction-{txn.id}")
    assert [e.version for e in loaded] == [1, 2, 3]
    assert loaded[0].event_type == "TransactionCreated"
    assert loaded[2].event_type == "PaymentFailed"


async def test_hash_chain_links_events(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=txn.pull_pending_events(),
    )
    await clean_event_store.commit()

    loaded = await repo.load_stream(stream_id=f"transaction-{txn.id}")
    assert loaded[0].previous_hash is None
    assert loaded[1].previous_hash == loaded[0].event_hash
    assert loaded[2].previous_hash == loaded[1].event_hash


async def test_optimistic_concurrency_conflict(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)
    events = txn.pull_pending_events()
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=events,
    )
    await clean_event_store.commit()

    # Build another event for the same stream, but claim version 0 again.
    txn.record_attempt(
        outcome=AttemptOutcome.SOFT_DECLINE,
        decline=DeclineInfo(
            code_raw="card_velocity_exceeded",
            code_normalized="VELOCITY",
            category=DeclineCategory.FRAUD,
        ),
    )
    bad_events = txn.pull_pending_events()
    with pytest.raises(ConcurrencyConflictError):
        await repo.append_events(
            stream_id=f"transaction-{txn.id}",
            expected_version=0,  # wrong — stream is already at version 3
            events=bad_events,
        )


async def test_outbox_rows_written_in_same_transaction(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)
    events = txn.pull_pending_events()
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=events,
    )
    await clean_event_store.commit()

    rows = (
        await clean_event_store.execute(
            select(OutboxModel).where(OutboxModel.tenant_id == txn.tenant_id)
        )
    ).scalars().all()
    assert len(rows) == len(events)
    assert all(r.status == "pending" for r in rows)
    assert all(r.destination == "redis-stream:transaction" for r in rows)


async def test_snapshot_roundtrip(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=txn.pull_pending_events(),
    )
    await repo.save_snapshot(
        stream_id=f"transaction-{txn.id}",
        stream_type="transaction",
        tenant_id=txn.tenant_id,
        version=3,
        state={"status": txn.status.value, "attempts": len(txn.attempts)},
    )
    await clean_event_store.commit()

    latest = await repo.load_latest_snapshot(stream_id=f"transaction-{txn.id}")
    assert latest is not None
    assert latest.version == 3
    assert latest.state["status"] == "failed"


async def test_materialize_stream_returns_typed_events(clean_event_store: AsyncSession) -> None:
    txn = _txn_with_attempt()
    tenant_id = txn.tenant_id
    repo = EventStoreRepository(clean_event_store)
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=txn.pull_pending_events(),
    )
    await clean_event_store.commit()

    events = await repo.materialize_stream(
        stream_id=f"transaction-{txn.id}", tenant_id=tenant_id
    )
    assert [type(e).__name__ for e in events] == [
        "TransactionCreated",
        "AttemptRecorded",
        "PaymentFailed",
    ]
    # Replay the aggregate from the materialized events — full round-trip.
    replayed = Transaction.replay(events)
    assert replayed.id == txn.id
    assert replayed.status.value == "failed"


async def test_db_trigger_blocks_update_on_events(clean_event_store: AsyncSession) -> None:
    """The audit.events table must reject UPDATE — defense in depth."""
    txn = _txn_with_attempt()
    repo = EventStoreRepository(clean_event_store)
    await repo.append_events(
        stream_id=f"transaction-{txn.id}",
        expected_version=0,
        events=txn.pull_pending_events(),
    )
    await clean_event_store.commit()

    with pytest.raises(Exception, match="immutable"):
        await clean_event_store.execute(
            text("UPDATE audit.events SET payload = '{}'::jsonb WHERE stream_id = :sid"),
            {"sid": f"transaction-{txn.id}"},
        )
        await clean_event_store.commit()
