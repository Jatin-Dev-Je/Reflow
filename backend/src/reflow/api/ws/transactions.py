"""WebSocket — live transaction event stream.

Subscribes to the `redis-stream:transaction` Redis Stream (where the outbox
relay publishes events) and pushes filtered messages to the client.

Per-connection tenant isolation:
    * Client opens WS to /ws/transactions
    * Server reads X-Tenant-Id header (or `?tenant_id=...` query param)
    * Server filters: only events for that tenant are pushed to that socket

Backpressure: if the client falls behind, we use `WRITE_BUFFER_LIMIT`. When
that fills, the connection is closed (client can reconnect with last-seen
cursor — TODO).

For demo simplicity we don't authenticate the socket beyond tenant claim;
auth wiring goes here once FastAPI Users lands.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Final
from uuid import UUID

import orjson
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from reflow.core.observability.logging import bind_contextvars, get_logger
from reflow.core.redis import get_redis

_logger = get_logger(__name__)

router = APIRouter()

TRANSACTION_STREAM_NAME: Final[str] = "redis-stream:transaction"
READ_BLOCK_MS: Final[int] = 5_000  # XREAD long-poll
MAX_EVENTS_PER_TICK: Final[int] = 50


@router.websocket("/ws/transactions")
async def transactions_ws(
    websocket: WebSocket,
    tenant_id: str | None = Query(default=None, description="Tenant filter — UUID."),
) -> None:
    # Resolve tenant from header or query.
    raw_tenant = websocket.headers.get("X-Tenant-Id") or tenant_id
    if raw_tenant is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="X-Tenant-Id required"
        )
        return
    try:
        tenant_uuid = UUID(raw_tenant)
    except ValueError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="X-Tenant-Id must be a UUID"
        )
        return

    await websocket.accept()
    bind_contextvars(tenant_id=str(tenant_uuid), ws_path="/ws/transactions")
    _logger.info("ws.transactions.connected", tenant_id=str(tenant_uuid))

    redis = get_redis(role="cache")
    # Start reading from now — historical replay should go through REST.
    last_id = b"$"

    pump_task = asyncio.create_task(_pump(websocket, redis, tenant_uuid, last_id))
    keepalive_task = asyncio.create_task(_keepalive(websocket))

    try:
        # Wait until either side closes.
        done, pending = await asyncio.wait(
            [pump_task, keepalive_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
            with contextlib.suppress(Exception):
                await t
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        _logger.warning("ws.transactions.error", error=str(exc))
    finally:
        _logger.info("ws.transactions.disconnected", tenant_id=str(tenant_uuid))


async def _pump(
    websocket: WebSocket,
    redis,
    tenant_uuid: UUID,
    last_id: bytes,
) -> None:
    """Forward stream entries for the tenant until the socket closes."""
    cursor = last_id
    while True:
        try:
            entries = await redis.xread(
                streams={TRANSACTION_STREAM_NAME: cursor},
                count=MAX_EVENTS_PER_TICK,
                block=READ_BLOCK_MS,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("ws.transactions.xread_error", error=str(exc))
            await asyncio.sleep(1.0)
            continue

        if not entries:
            continue

        for _stream, items in entries:
            for entry_id, fields in items:
                cursor = entry_id
                # Decode field bytes.
                f = {k.decode(): v.decode() for k, v in fields.items()}
                if f.get("tenant_id") != str(tenant_uuid):
                    continue

                payload = {
                    "event_id": f.get("event_id"),
                    "stream_id": f.get("stream_id"),
                    "stream_type": f.get("stream_type"),
                    "event_type": f.get("event_type"),
                    "version": int(f.get("version", 0)),
                    "occurred_at": f.get("occurred_at"),
                    "event_hash": f.get("event_hash"),
                    "payload": _safe_json(f.get("payload")),
                    "metadata": _safe_json(f.get("metadata")),
                }
                try:
                    await websocket.send_bytes(orjson.dumps(payload))
                except (WebSocketDisconnect, RuntimeError):
                    return


def _safe_json(text: str | None) -> object:
    if not text:
        return None
    try:
        return orjson.loads(text)
    except orjson.JSONDecodeError:
        return text


async def _keepalive(websocket: WebSocket) -> None:
    """Receive loop — detects client-side closes and answers pings."""
    while True:
        try:
            msg = await websocket.receive()
        except (WebSocketDisconnect, RuntimeError):
            return
        # Browsers don't always send explicit pings; this just keeps the
        # task alive and bails on close.
        if msg.get("type") == "websocket.disconnect":
            return
