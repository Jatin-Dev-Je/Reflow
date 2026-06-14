"""Structured logging via structlog.

Two key properties:
  1. Every log entry carries the bound context (tenant_id, trace_id,
     correlation_id, ...) from `structlog.contextvars`.
  2. Output is JSON in non-dev environments; pretty console output in dev.

Initialise once at process startup via `configure_logging()`.
Get a logger anywhere via `get_logger(__name__)`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from reflow.core.config import LogFormat, ObservabilitySettings


def _drop_color_message(_: object, __: str, event_dict: EventDict) -> EventDict:
    """Uvicorn duplicates 'message' under 'color_message'; we don't want both."""
    event_dict.pop("color_message", None)
    return event_dict


def _build_processors(settings: ObservabilitySettings) -> list[Processor]:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _drop_color_message,
    ]

    if settings.log_format == LogFormat.JSON:
        shared.append(structlog.processors.dict_tracebacks)
        shared.append(structlog.processors.JSONRenderer(serializer=_json_dumps))
    else:
        shared.append(structlog.dev.ConsoleRenderer(colors=True))

    return shared


def _json_dumps(obj: Any, **kwargs: Any) -> str:
    # orjson returns bytes; structlog expects str.
    import orjson

    return orjson.dumps(obj).decode()


def configure_logging(settings: ObservabilitySettings | None = None) -> None:
    """Configure structlog + stdlib logging. Idempotent — safe to call repeatedly."""
    if settings is None:
        settings = ObservabilitySettings()

    processors = _build_processors(settings)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level.value]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Pipe stdlib logging (uvicorn, sqlalchemy, ...) through structlog formatting.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=processors[:-1],  # all but the final renderer
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                processors[-1],
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.value)

    # Quiet down chatty libraries.
    for noisy in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger. Pass `__name__` from caller modules."""
    return structlog.get_logger(name)


# Re-export the contextvars binders so callers can attach correlation IDs etc.
bind_contextvars = structlog.contextvars.bind_contextvars
unbind_contextvars = structlog.contextvars.unbind_contextvars
clear_contextvars = structlog.contextvars.clear_contextvars
