"""JWT encode/decode for auth tokens.

We issue two tokens:
    * access  — short-lived (default 60min), used for every API call
    * refresh — longer-lived (default 30d), used only to mint new access tokens

Tokens are HS256-signed with the secret from SecuritySettings.jwt_secret.
We never put PII in the payload — only user_id, tenant_id, and standard
JWT claims (iat, exp, jti, typ).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from reflow.core.config import SecuritySettings, get_settings
from reflow.core.exceptions import DomainError


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class InvalidAuthTokenError(DomainError):
    error_code = "auth.invalid_token"
    http_status = 401


def encode_token(
    *,
    token_type: TokenType,
    user_id: UUID,
    tenant_id: UUID | None,
    settings: SecuritySettings | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    settings = settings or get_settings().security
    now = datetime.now(UTC)
    if token_type == TokenType.ACCESS:
        exp = now + timedelta(minutes=settings.jwt_access_expires_minutes)
    else:
        exp = now + timedelta(days=settings.jwt_refresh_expires_days)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "typ": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, *, settings: SecuritySettings | None = None) -> dict[str, Any]:
    settings = settings or get_settings().security
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise InvalidAuthTokenError(f"Invalid token: {exc}") from exc


def assert_token_type(payload: dict[str, Any], expected: TokenType) -> None:
    if payload.get("typ") != expected.value:
        raise InvalidAuthTokenError(
            f"Token type mismatch: expected {expected.value!r}, "
            f"got {payload.get('typ')!r}"
        )
