"""Request-ID middleware.

Generates (or accepts) an X-Request-ID per request, binds it to the structlog
context for the duration of the request, and echoes it in the response so
clients can correlate.
"""

from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from reflow.core.observability.logging import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            clear_contextvars()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
