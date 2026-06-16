"""WebSocket — live approval requests stream.

Pushes RecoveryApprovalRequested events so a HITL dashboard can light up
the queue in real time.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket

from reflow.api.ws.base import serve_filtered_stream

router = APIRouter()


@router.websocket("/ws/approvals")
async def approvals_ws(
    websocket: WebSocket,
    tenant_id: str | None = Query(default=None, description="Tenant filter — UUID."),
) -> None:
    # Approval requests live on the recovery stream — we filter at the client
    # by event_type=='RecoveryApprovalRequested' (lightweight; same stream).
    # When traffic justifies it we'll move approvals to a dedicated stream.
    await serve_filtered_stream(
        websocket,
        stream_name="redis-stream:recovery",
        tenant_id_param=tenant_id,
        channel_label="approvals",
    )
