"""Password hashing + JWT encode/decode."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from reflow.core.config import SecuritySettings
from reflow.core.exceptions import DomainError
from reflow.core.security.jwt import (
    InvalidAuthTokenError,
    TokenType,
    assert_token_type,
    decode_token,
    encode_token,
)
from reflow.core.security.passwords import (
    hash_password,
    needs_rehash,
    verify_password,
)
from pydantic import SecretStr

pytestmark = pytest.mark.unit


def _settings() -> SecuritySettings:
    # >=32 bytes for HS256 — passes the InsecureKeyLengthWarning check.
    return SecuritySettings(jwt_secret=SecretStr("test-secret-with-at-least-32-bytes!!"))


# -----------------------------------------------------------------------------
# Passwords
# -----------------------------------------------------------------------------


class TestPasswords:
    def test_hash_then_verify_roundtrip(self) -> None:
        h = hash_password("hunter2-and-then-some")
        assert verify_password("hunter2-and-then-some", h)

    def test_wrong_password_fails(self) -> None:
        h = hash_password("hunter2-and-then-some")
        assert not verify_password("wrong", h)

    def test_empty_password_rejected_in_hash(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            hash_password("")

    def test_empty_password_returns_false_in_verify(self) -> None:
        assert not verify_password("", "any-hash")

    def test_malformed_hash_returns_false(self) -> None:
        assert not verify_password("anything", "not-a-real-hash")

    def test_different_hashes_for_same_password(self) -> None:
        # argon2 includes random salt -> different output every time
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1)
        assert verify_password("same-password", h2)

    def test_needs_rehash_returns_boolean(self) -> None:
        h = hash_password("test-password")
        # Fresh hash should not need rehash
        assert needs_rehash(h) is False


# -----------------------------------------------------------------------------
# JWT
# -----------------------------------------------------------------------------


class TestJWT:
    def test_access_token_roundtrip(self) -> None:
        settings = _settings()
        user_id = uuid4()
        tenant_id = uuid4()
        token = encode_token(
            token_type=TokenType.ACCESS,
            user_id=user_id,
            tenant_id=tenant_id,
            settings=settings,
        )
        payload = decode_token(token, settings=settings)
        assert payload["sub"] == str(user_id)
        assert payload["tid"] == str(tenant_id)
        assert payload["typ"] == "access"
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_refresh_token_has_longer_expiry(self) -> None:
        settings = _settings()
        user_id = uuid4()

        access = encode_token(
            token_type=TokenType.ACCESS, user_id=user_id, tenant_id=None, settings=settings
        )
        refresh = encode_token(
            token_type=TokenType.REFRESH, user_id=user_id, tenant_id=None, settings=settings
        )
        access_payload = decode_token(access, settings=settings)
        refresh_payload = decode_token(refresh, settings=settings)
        assert refresh_payload["exp"] > access_payload["exp"]

    def test_decode_with_wrong_secret_fails(self) -> None:
        good = _settings()
        bad = SecuritySettings(jwt_secret=SecretStr("some-other-secret-with-32-plus-bytes!"))
        token = encode_token(
            token_type=TokenType.ACCESS,
            user_id=uuid4(),
            tenant_id=None,
            settings=good,
        )
        with pytest.raises(InvalidAuthTokenError):
            decode_token(token, settings=bad)

    def test_decode_expired_token_fails(self) -> None:
        settings = _settings()
        user_id = uuid4()
        # Manually craft an expired token by setting jwt_access_expires_minutes
        # to a negative value via a copy.
        custom = SecuritySettings(
            jwt_secret=settings.jwt_secret, jwt_access_expires_minutes=1
        )
        import jwt as pyjwt
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "tid": None,
            "typ": "access",
            "iat": int(now.timestamp()),
            "exp": int((now - timedelta(seconds=10)).timestamp()),
            "jti": "x",
        }
        token = pyjwt.encode(
            payload,
            custom.jwt_secret.get_secret_value(),
            algorithm=custom.jwt_algorithm,
        )
        with pytest.raises(InvalidAuthTokenError):
            decode_token(token, settings=custom)

    def test_token_type_mismatch_raises(self) -> None:
        settings = _settings()
        token = encode_token(
            token_type=TokenType.ACCESS,
            user_id=uuid4(),
            tenant_id=None,
            settings=settings,
        )
        payload = decode_token(token, settings=settings)
        with pytest.raises(InvalidAuthTokenError, match="type mismatch"):
            assert_token_type(payload, TokenType.REFRESH)

    def test_token_type_match_passes(self) -> None:
        settings = _settings()
        token = encode_token(
            token_type=TokenType.REFRESH,
            user_id=uuid4(),
            tenant_id=None,
            settings=settings,
        )
        payload = decode_token(token, settings=settings)
        assert_token_type(payload, TokenType.REFRESH)  # does not raise

    def test_invalid_token_error_inherits_domain_error(self) -> None:
        assert issubclass(InvalidAuthTokenError, DomainError)
        # Status 401 — caller can rely on this.
        try:
            decode_token("not-a-jwt", settings=_settings())
        except InvalidAuthTokenError as exc:
            assert exc.http_status == 401
        else:
            pytest.fail("expected InvalidAuthTokenError")
