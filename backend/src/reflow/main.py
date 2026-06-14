"""FastAPI application factory and lifespan management.

Construction is a function (`create_app`) so tests can build isolated apps with
overridden settings, and so reloaders work cleanly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from reflow import __version__
from reflow.core.config import Settings, get_settings
from reflow.core.database import dispose_engine, init_engine
from reflow.core.middleware import RequestIdMiddleware, install_error_handlers
from reflow.core.observability.logging import configure_logging, get_logger
from reflow.core.redis import close_redis_clients, ping_redis

_logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings.observability)
    _logger.info("app.starting", env=settings.env.value, version=__version__)

    init_engine(settings.database)
    # Eager-ping Redis so a misconfigured deploy fails loudly at boot, not on first request.
    await ping_redis()

    try:
        yield
    finally:
        _logger.info("app.shutting_down")
        await close_redis_clients()
        await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.observability)

    app = FastAPI(
        title="Reflow Backend",
        version=__version__,
        default_response_class=ORJSONResponse,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=_lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    # ---- Health endpoints ---------------------------------------------------
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness: process is up."""
        return {"status": "ok", "version": __version__}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> dict[str, object]:
        """Readiness: dependencies are healthy."""
        redis_ok = await ping_redis()
        return {
            "status": "ok" if redis_ok else "degraded",
            "checks": {"redis": redis_ok},
        }

    return app
