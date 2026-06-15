"""Mock gateway — deterministic, in-process, no network.

Used by:
    * The simulator (drives baseline + Reflow lanes through the same code).
    * Local dev (no need for Stripe test keys).
    * Integration tests (no flakiness from external services).

Behaviour is deterministic given a seed: same (recovery_id, attempt_number,
gateway_id) always produces the same outcome. This means a simulation can
re-run identically.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from reflow.infrastructure.simulation.distributions import (
    DEFAULT_RECOVERY_PROBABILITY,
    recovery_probability,
)


@dataclass(frozen=True, slots=True)
class MockChargeRequest:
    idempotency_key: str
    amount_cents: int
    currency: str
    card_bin: str
    decline_code_normalized: str   # set when initial attempt; absent on retries
    strategy_kind: str | None       # for retries — drives the success roll
    seed: int = 0


@dataclass(frozen=True, slots=True)
class MockChargeResponse:
    success: bool
    decline_code: str | None
    latency_ms: int
    cost_cents: int = 0


def _deterministic_roll(idempotency_key: str, seed: int) -> float:
    """Map (idempotency_key, seed) -> a uniform [0, 1) value."""
    h = hashlib.sha256(f"{seed}:{idempotency_key}".encode()).digest()
    n = int.from_bytes(h[:8], "big")
    return n / 2**64


class MockGateway:
    """A 'gateway' the simulator + dev environments can call.

    For an initial attempt with a decline_code_normalized: always fails with
    that decline (this is the failure we're simulating).

    For a retry (strategy_kind set): rolls success based on
    RECOVERY_PROBABILITIES.
    """

    def __init__(self, *, seed: int = 0) -> None:
        self._seed = seed

    async def charge(self, req: MockChargeRequest) -> MockChargeResponse:
        # Retry — roll against the strategy's historical recovery rate.
        if req.strategy_kind is not None:
            p = recovery_probability(
                req.decline_code_normalized, req.strategy_kind
            ) or DEFAULT_RECOVERY_PROBABILITY
            roll = _deterministic_roll(req.idempotency_key, self._seed)
            if roll < p:
                return MockChargeResponse(
                    success=True,
                    decline_code=None,
                    latency_ms=120,
                    cost_cents=_fee(req.amount_cents),
                )
            return MockChargeResponse(
                success=False,
                decline_code=req.decline_code_normalized,
                latency_ms=110,
            )

        # Initial attempt: deterministic decline.
        return MockChargeResponse(
            success=False,
            decline_code=req.decline_code_normalized,
            latency_ms=80,
        )


def _fee(amount_cents: int) -> int:
    """Approximate 2.9% + $0.30 fee."""
    return int(amount_cents * 0.029) + 30
