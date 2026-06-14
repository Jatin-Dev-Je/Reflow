"""Error-handler registration.

Maps `ReflowError` subclasses to their declared HTTP status and a stable JSON
shape. Anything not derived from `ReflowError` falls through to FastAPI's
default 500 handler — that's a bug we want to fix in code, not paper over.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from reflow.core.exceptions import ReflowError
from reflow.core.observability.logging import get_logger

_logger = get_logger(__name__)


async def _reflow_error_handler(_: Request, exc: Exception) -> ORJSONResponse:
    # The signature uses Exception for FastAPI compatibility; we narrow inside.
    assert isinstance(exc, ReflowError)  # noqa: S101 — handler is only registered for ReflowError
    _logger.warning(
        "request.failed",
        error_code=exc.error_code,
        message=exc.message,
        context=exc.context,
        exc_info=exc.http_status >= 500,
    )
    return ORJSONResponse(status_code=exc.http_status, content={"error": exc.to_dict()})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ReflowError, _reflow_error_handler)
