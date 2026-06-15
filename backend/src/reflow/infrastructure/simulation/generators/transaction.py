"""Generate synthetic failed transactions for the simulator."""

from __future__ import annotations

import random
from collections.abc import Iterator

from reflow.infrastructure.simulation.distributions import (
    FailureSpec,
    sample_amount_cents,
    sample_decline,
    sample_gateway,
    sample_issuer,
)


def generate_failures(*, count: int, seed: int) -> Iterator[FailureSpec]:
    """Yield `count` seeded synthetic failures."""
    rng = random.Random(seed)
    for i in range(count):
        amount = sample_amount_cents(rng)
        gateway = sample_gateway(rng)
        bin_, issuer = sample_issuer(rng)
        code, category, is_soft = sample_decline(rng)
        yield FailureSpec(
            external_id=f"sim_{seed}_{i:08d}",
            amount_cents=amount,
            currency="USD",
            card_bin=bin_,
            issuer_id=issuer,
            gateway_provider=gateway,
            decline_code_normalized=code,
            decline_category=category,
            is_soft_decline=is_soft,
        )
