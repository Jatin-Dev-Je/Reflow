"""Shared WebSocket stream subscriber.

All WS channels follow the same pattern: subscribe to a Redis Stream, filter
entries by tenant_id, forward as JSON. Centralizing the loop keeps each
per-channel route file tiny.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Final
from uuid import UUID

import orjson
from fastapi import WebSocket, WebSocketDisconnect, status

from reflow.core.observability.logging import bind_contextvars, get_logger
from reflow.core.redis import get_redis

_logger = get_logger(__name__)

READ_BLOCK_MS: Final[int] = 5_000
MAX_EVENTS_PER_TICK: Final[int] = 50


async def serve_filtered_stream(
    websocket: WebSocket,
    *,
    stream_name: str,
    tenant_id_param: str | None,
    channel_label: str,
) -> None:
    """Accept the socket, validate tenant, subscribe, fan out, clean up."""
    raw_tenant = websocket.headers.get("X-Tenant-Id") or tenant_id_param
    if raw_tenant is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="X-Tenant-Id required",
        )
        return
    try:
        tenant_uuid = UUID(raw_tenant)
    except ValueError:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="X-Tenant-Id must be a UUID",
        )
        return

    await websocket.accept()
    bind_contextvars(tenant_id=str(tenant_uuid), ws_channel=channel_label)
    _logger.info("ws.connected", channel=channel_label, tenant_id=str(tenant_uuid))

    redis = get_redis(role="cache")
    cursor = b"$"

    pump_task = asyncio.create_task(
        _pump(websocket, redis, tenant_uuid, stream_name, cursor)
    )
    keepalive_task = asyncio.create_task(_keepalive(websocket))

    try:
        done, pending = await asyncio.wait(
            [pump_task, keepalive_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
            with contextlib.suppress(Exception):
                await t
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — never crash the worker on a single connection
        _logger.warning("ws.error", channel=channel_label, error=str(exc))
    finally:
        _logger.info(
            "ws.disconnected", channel=channel_label, tenant_id=str(tenant_uuid)
        )


async def _pump(
    websocket: WebSocket,
    redis,
    tenant_uuid: UUID,
    stream_name: str,
    cursor: bytes,
) -> None:
    current = cursor
    while True:
        try:
            entries = await redis.xread(
                streams={stream_name: current},
                count=MAX_EVENTS_PER_TICK,
                block=READ_BLOCK_MS,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("ws.xread_error", stream=stream_name, error=str(exc))
            await asyncio.sleep(1.0)
            continue

        if not entries:
            continue

        for _stream, items in entries:
            for entry_id, fields in items:
                current = entry_id
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
    while True:
        try:
            msg = await websocket.receive()
        except (WebSocketDisconnect, RuntimeError):
            return
        if msg.get("type") == "websocket.disconnect":
            return
