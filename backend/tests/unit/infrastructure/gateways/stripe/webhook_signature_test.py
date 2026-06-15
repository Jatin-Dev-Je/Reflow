"""Stripe webhook signature verification — security-critical, fully tested.

Property: a well-formed valid signature must pass; everything else must fail.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from reflow.infrastructure.gateways.stripe.webhooks import (
    InvalidSignatureError,
    parse_signature_header,
    verify_signature,
)

pytestmark = pytest.mark.unit


def _sign(payload: bytes, secret: str, timestamp: int) -> str:
    msg = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def _header(timestamp: int, sigs: list[str]) -> str:
    parts = [f"t={timestamp}", *[f"v1={s}" for s in sigs]]
    return ",".join(parts)


SECRET = "whsec_test_super_secret"
PAYLOAD = b'{"type":"charge.failed","id":"evt_123"}'


class TestParse:
    def test_parses_well_formed_header(self) -> None:
        parsed = parse_signature_header("t=1700000000,v1=abc,v1=def,v0=xyz")
        assert parsed.timestamp == 1700000000
        assert parsed.v1_signatures == ("abc", "def")

    def test_missing_timestamp_rejected(self) -> None:
        with pytest.raises(InvalidSignatureError, match="timestamp"):
            parse_signature_header("v1=abc")

    def test_missing_v1_rejected(self) -> None:
        with pytest.raises(InvalidSignatureError, match="v1"):
            parse_signature_header("t=1700000000")

    def test_empty_header_rejected(self) -> None:
        with pytest.raises(InvalidSignatureError):
            parse_signature_header("")

    def test_malformed_timestamp_rejected(self) -> None:
        with pytest.raises(InvalidSignatureError, match="timestamp"):
            parse_signature_header("t=notanumber,v1=abc")


class TestVerify:
    def test_valid_signature_passes(self) -> None:
        ts = int(time.time())
        sig = _sign(PAYLOAD, SECRET, ts)
        verify_signature(
            payload=PAYLOAD, header=_header(ts, [sig]), secret=SECRET, now=ts
        )

    def test_tampered_payload_fails(self) -> None:
        ts = int(time.time())
        sig = _sign(PAYLOAD, SECRET, ts)
        with pytest.raises(InvalidSignatureError, match="match"):
            verify_signature(
                payload=b"different payload",
                header=_header(ts, [sig]),
                secret=SECRET,
                now=ts,
            )

    def test_wrong_secret_fails(self) -> None:
        ts = int(time.time())
        sig = _sign(PAYLOAD, "other_secret", ts)
        with pytest.raises(InvalidSignatureError, match="match"):
            verify_signature(
                payload=PAYLOAD, header=_header(ts, [sig]), secret=SECRET, now=ts
            )

    def test_old_timestamp_fails_replay_defense(self) -> None:
        ts = int(time.time())
        sig = _sign(PAYLOAD, SECRET, ts - 10_000)
        with pytest.raises(InvalidSignatureError, match="tolerance"):
            verify_signature(
                payload=PAYLOAD,
                header=_header(ts - 10_000, [sig]),
                secret=SECRET,
                now=ts,
            )

    def test_future_timestamp_fails(self) -> None:
        ts = int(time.time())
        sig = _sign(PAYLOAD, SECRET, ts + 10_000)
        with pytest.raises(InvalidSignatureError, match="tolerance"):
            verify_signature(
                payload=PAYLOAD,
                header=_header(ts + 10_000, [sig]),
                secret=SECRET,
                now=ts,
            )

    def test_multiple_v1_signatures_any_match_passes(self) -> None:
        ts = int(time.time())
        good = _sign(PAYLOAD, SECRET, ts)
        bad = "00" * 32
        verify_signature(
            payload=PAYLOAD, header=_header(ts, [bad, good]), secret=SECRET, now=ts
        )

    def test_constant_time_compare_used(self) -> None:
        # Smoke test that we don't short-circuit on prefix mismatch — we can't
        # measure timing directly, but we ensure that mismatching sigs are
        # rejected rather than crashing.
        ts = int(time.time())
        with pytest.raises(InvalidSignatureError):
            verify_signature(
                payload=PAYLOAD,
                header=_header(ts, ["ab" * 32]),
                secret=SECRET,
                now=ts,
            )
