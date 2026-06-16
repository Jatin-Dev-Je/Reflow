"""WebSocket — live recovery state-change stream.

Subscribes to redis-stream:recovery where outbox-published events for the
recovery aggregate appear (RecoveryCreated, RecoveryDiagnosed, ...
RecoverySucceeded).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket

from reflow.api.ws.base import serve_filtered_stream

router = APIRouter()


@router.websocket("/ws/recoveries")
async def recoveries_ws(
    websocket: WebSocket,
    tenant_id: str | None = Query(default=None, description="Tenant filter — UUID."),
) -> None:
    await serve_filtered_stream(
        websocket,
        stream_name="redis-stream:recovery",
        tenant_id_param=tenant_id,
        channel_label="recoveries",
    )
