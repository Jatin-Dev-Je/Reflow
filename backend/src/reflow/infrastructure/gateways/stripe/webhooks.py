"""Stripe webhook signature verification.

Implements the same constant-time HMAC-SHA256 verification scheme Stripe
uses (see https://stripe.com/docs/webhooks/signatures). The header looks
like:

    Stripe-Signature: t=1234567890,v1=abc...,v1=def...

We extract the timestamp + every v1 signature, reject if no v1 found,
reject if timestamp drift exceeds the tolerance window (replay defense),
and accept if any v1 signature matches HMAC(secret, "<t>.<payload>").
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Final

from reflow.core.exceptions import DomainError

# Default tolerance: 5 minutes. Stripe's recommended value.
DEFAULT_TOLERANCE_SECONDS: Final[int] = 5 * 60


class InvalidSignatureError(DomainError):
    error_code = "infrastructure.invalid_webhook_signature"
    http_status = 400


@dataclass(frozen=True, slots=True)
class ParsedSignature:
    timestamp: int
    v1_signatures: tuple[str, ...]


def parse_signature_header(header: str) -> ParsedSignature:
    """Parse `Stripe-Signature` header. Raise InvalidSignatureError on malformed input."""
    if not header:
        raise InvalidSignatureError("Stripe-Signature header is empty")

    timestamp: int | None = None
    v1: list[str] = []
    for item in header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError as exc:
                raise InvalidSignatureError(f"Bad timestamp in signature: {value!r}") from exc
        elif key == "v1":
            v1.append(value)
        # Unknown schemes (e.g. v0) ignored — we only trust v1.

    if timestamp is None:
        raise InvalidSignatureError("Stripe-Signature missing timestamp (t=...)")
    if not v1:
        raise InvalidSignatureError("Stripe-Signature missing v1 signature")
    return ParsedSignature(timestamp=timestamp, v1_signatures=tuple(v1))


def verify_signature(
    *,
    payload: bytes,
    header: str,
    secret: str,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> None:
    """Verify the webhook signature or raise InvalidSignatureError.

    `now` is injectable for tests; production passes None and we use time.time().
    """
    parsed = parse_signature_header(header)

    current = int(now if now is not None else time.time())
    # Two-sided drift check — replay defense.
    if abs(current - parsed.timestamp) > tolerance_seconds:
        raise InvalidSignatureError(
            "Stripe-Signature timestamp outside tolerance window",
            context={
                "timestamp": parsed.timestamp,
                "now": current,
                "tolerance_seconds": tolerance_seconds,
            },
        )

    signed_payload = f"{parsed.timestamp}.".encode() + payload
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()

    # Constant-time comparison vs each provided v1.
    for v1 in parsed.v1_signatures:
        if hmac.compare_digest(expected, v1):
            return

    raise InvalidSignatureError("Stripe-Signature did not match any v1 signature")
