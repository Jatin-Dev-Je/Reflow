"""End-to-end HTTP test of the mock-gateway -> transaction -> timeline flow.

Spins up Postgres via testcontainers, runs the FastAPI app against it via
httpx ASGITransport, and verifies the full pipeline:

    1. POST /api/webhooks/mock-gateway with a soft decline
    2. GET /api/v1/transactions/{id} returns status='failed'
    3. GET /api/v1/transactions/{id}/attempts shows one attempt
    4. GET /api/v1/transactions/{id}/timeline shows
       TransactionCreated -> AttemptRecorded -> PaymentFailed
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def app_client(database_url: str, redis_url: str):
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url

    from reflow.core.config import reset_settings_cache
    from reflow.core.database import dispose_engine

    reset_settings_cache()
    # Make sure any prior engine is disposed so the new URL is picked up.
    await dispose_engine()

    from reflow.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dispose_engine()


async def test_mock_gateway_to_timeline(app_client: AsyncClient) -> None:
    body = {
        "external_id": "tx_e2e_001",
        "amount_cents": 4999,
        "currency": "USD",
        "card": {
            "bin": "424242",
            "last4": "4242",
            "brand": "visa",
            "funding": "credit",
            "country": "US",
        },
        "gateway_provider": "mock",
        "outcome": "soft_decline",
        "decline": {
            "code_raw": "insufficient_funds",
            "code_normalized": "FUNDS_INSUFFICIENT",
            "category": "funds",
            "message": "Insufficient funds",
        },
    }
    r = await app_client.post("/api/webhooks/mock-gateway", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created_new_transaction"] is True
    assert data["status"] == "failed"
    assert data["attempt_number"] == 1
    txn_id = data["transaction_id"]

    # Single transaction
    r = await app_client.get(f"/api/v1/transactions/{txn_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert r.json()["amount_cents"] == 4999

    # Attempts
    r = await app_client.get(f"/api/v1/transactions/{txn_id}/attempts")
    assert r.status_code == 200
    attempts = r.json()
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "soft_decline"
    assert attempts[0]["decline_code_normalized"] == "FUNDS_INSUFFICIENT"

    # Timeline
    r = await app_client.get(f"/api/v1/transactions/{txn_id}/timeline")
    assert r.status_code == 200
    timeline = r.json()
    assert [e["event_type"] for e in timeline] == [
        "TransactionCreated",
        "AttemptRecorded",
        "PaymentFailed",
    ]


async def test_second_webhook_for_same_external_id_appends_attempt(
    app_client: AsyncClient,
) -> None:
    base = {
        "external_id": "tx_e2e_two_attempts",
        "amount_cents": 1500,
        "currency": "USD",
        "card": {
            "bin": "424242",
            "last4": "4242",
            "brand": "visa",
            "funding": "credit",
            "country": "US",
        },
        "gateway_provider": "mock",
        "outcome": "soft_decline",
        "decline": {
            "code_raw": "do_not_honor",
            "code_normalized": "ISSUER_DO_NOT_HONOR",
            "category": "issuer",
        },
    }

    r1 = await app_client.post("/api/webhooks/mock-gateway", json=base)
    assert r1.status_code == 200
    txn_id = r1.json()["transaction_id"]
    assert r1.json()["created_new_transaction"] is True
    assert r1.json()["attempt_number"] == 1

    r2 = await app_client.post("/api/webhooks/mock-gateway", json=base)
    assert r2.status_code == 200, r2.text
    # FAILED is not terminal — a second attempt is recorded as #2 on the same txn.
    assert r2.json()["transaction_id"] == txn_id
    assert r2.json()["created_new_transaction"] is False
    assert r2.json()["attempt_number"] == 2

    # Verify the timeline now contains both attempts.
    timeline = (await app_client.get(f"/api/v1/transactions/{txn_id}/timeline")).json()
    attempt_events = [e for e in timeline if e["event_type"] == "AttemptRecorded"]
    assert len(attempt_events) == 2
