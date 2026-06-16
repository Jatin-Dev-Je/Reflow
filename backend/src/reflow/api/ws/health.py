"""WebSocket — live gateway / issuer health stream.

Pushes health.* events as the rollup worker produces them
(GatewayHealthSampled, GatewayOutageDetected, IssuerHealthSampled, ...).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket

from reflow.api.ws.base import serve_filtered_stream

router = APIRouter()


@router.websocket("/ws/health")
async def health_ws(
    websocket: WebSocket,
    tenant_id: str | None = Query(default=None, description="Tenant filter — UUID."),
) -> None:
    await serve_filtered_stream(
        websocket,
        stream_name="redis-stream:health",
        tenant_id_param=tenant_id,
        channel_label="health",
    )
