"""HTTP-level idempotency middleware.

For mutating endpoints (POST/PUT/PATCH/DELETE), clients send an
`Idempotency-Key` header. The middleware:

    1. On first request with a key — runs the handler, caches the response
       (status + headers + body), returns it.
    2. On retry with same key + same body — returns the cached response
       without invoking the handler.
    3. On retry with same key but DIFFERENT body — returns 422 (this is a
       client bug — different operations must use different keys).
    4. On a request in flight with the same key — returns 409 (concurrent
       retry; the client should wait).

Why three layers (HTTP + command + gateway)? See ADR-0005.

Storage: Redis with TTL set from SecuritySettings.idempotency_ttl_hours.
Failure modes:
    * Redis unavailable — middleware fails open (allows the request through).
      Lower-layer idempotency still protects correctness; HTTP layer is for
      replay friendliness, not safety.
"""

from __future__ import annotations

import json
from typing import Final

import orjson
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from reflow.core.config import SecuritySettings
from reflow.core.observability.logging import get_logger
from reflow.core.redis import get_redis
from reflow.core.security.signing import sha256_hex

_logger = get_logger(__name__)

IDEMPOTENCY_KEY_HEADER: Final[str] = "Idempotency-Key"
_IN_FLIGHT_MARKER: Final[str] = "in_flight"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        security: SecuritySettings,
        redis_client: Redis | None = None,
    ) -> None:
        super().__init__(app)
        self._security = security
        self._redis = redis_client  # injectable for tests
        self._required_methods = set(security.idempotency_required_methods)
        self._ttl_seconds = security.idempotency_ttl_hours * 3600

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        method = request.method
        if method not in self._required_methods:
            return await call_next(request)

        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if idempotency_key is None:
            # Don't break health probes / webhooks that don't yet supply a key.
            # In a production hardening pass we'd return 400 here, but for the
            # demo we trace and continue.
            _logger.debug(
                "idempotency.missing_key",
                method=method,
                path=request.url.path,
            )
            return await call_next(request)

        body = await request.body()
        request_hash = sha256_hex(body or b"")
        tenant_id = request.headers.get("X-Tenant-Id", "anon")
        key = _key(tenant_id, idempotency_key)

        redis = self._redis or get_redis(role="cache")
        try:
            cached_raw = await redis.get(key)
        except Exception as exc:  # noqa: BLE001 — fail open
            _logger.warning("idempotency.redis_unavailable_fail_open", error=str(exc))
            return await call_next(request)

        if cached_raw is not None:
            cached = json.loads(cached_raw)
            if cached.get("state") == _IN_FLIGHT_MARKER:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "error_code": "domain.idempotency_in_flight",
                            "message": "An identical request with this Idempotency-Key is in flight.",
                        }
                    },
                )
            if cached.get("request_hash") != request_hash:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "error_code": "domain.idempotency_conflict",
                            "message": (
                                "Idempotency-Key was reused with a different request body."
                            ),
                        }
                    },
                )
            return _replay_response(cached)

        # Mark in-flight (short TTL) and proceed.
        await redis.set(
            key,
            json.dumps({"state": _IN_FLIGHT_MARKER, "request_hash": request_hash}),
            ex=60,
        )

        # Recreate request body for the downstream handler (consumed by .body()).
        async def _receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]  # noqa: SLF001 — Starlette idiom
        response = await call_next(request)

        # Cache the completed response.
        body_chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body_chunks.append(chunk)
        response_body = b"".join(body_chunks)

        try:
            payload = json.dumps(
                {
                    "state": "completed",
                    "request_hash": request_hash,
                    "status_code": response.status_code,
                    "headers": {k.decode(): v.decode() for k, v in response.raw_headers},
                    "body": response_body.decode("utf-8", errors="replace"),
                }
            )
            await redis.set(key, payload, ex=self._ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("idempotency.cache_write_failed", error=str(exc))

        # Rebuild a fresh Response since we exhausted the body iterator.
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


def _key(tenant_id: str, idempotency_key: str) -> str:
    return f"idempotency:{tenant_id}:{idempotency_key}"


def _replay_response(cached: dict) -> Response:
    body = cached.get("body", "").encode("utf-8")
    headers = cached.get("headers", {})
    # Drop hop-by-hop headers we shouldn't replay.
    for hop in ("content-length", "transfer-encoding", "connection"):
        headers.pop(hop, None)
    return Response(
        content=body,
        status_code=cached.get("status_code", 200),
        headers=headers,
    )


# Convenience for tests / non-middleware code that wants the canonical hash function.
def canonical_request_hash(body: bytes) -> str:
    return sha256_hex(orjson.dumps(orjson.loads(body))) if body else sha256_hex(b"")
