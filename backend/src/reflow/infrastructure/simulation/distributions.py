"""Distributions used by the simulator.

These are *plausible* distributions derived from public Stripe / Visa
documentation, not exact reproductions. They're stable and reproducible
under a seed — the entire point of the harness is reproducibility.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# Public decline-code distribution shape (approximate).
# Categories taken from our DeclineCategory enum; weights sum to 100 across
# soft + hard declines combined.
DECLINE_CODE_WEIGHTS: list[tuple[str, str, int]] = [
    # (normalized_code, category, weight)
    ("FUNDS_INSUFFICIENT",   "funds",          22),
    ("ISSUER_DO_NOT_HONOR",  "issuer",         18),
    ("ISSUER_GENERIC_DECLINE", "issuer",       12),
    ("AUTH_3DS_REQUIRED",    "authentication",  9),
    ("FRAUD_SUSPECTED",      "fraud",           8),
    ("GATEWAY_TIMEOUT",      "gateway",         6),
    ("GATEWAY_ERROR",        "gateway",         6),
    ("CARD_EXPIRED",         "issuer",          5),
    ("CVV_FAILED",           "authentication",  4),
    ("VELOCITY",             "fraud",           4),
    ("NETWORK_REJECTED",     "network",         3),
    ("CARD_LOST_STOLEN",     "fraud",           2),
    ("PROCESSOR_DOWN",       "gateway",         1),
]
assert sum(w for _, _, w in DECLINE_CODE_WEIGHTS) == 100


# Soft vs hard decline mapping — soft codes are recoverable, hard codes
# are not (generally).
SOFT_DECLINE_CODES: frozenset[str] = frozenset(
    {
        "FUNDS_INSUFFICIENT",
        "ISSUER_DO_NOT_HONOR",
        "ISSUER_GENERIC_DECLINE",
        "AUTH_3DS_REQUIRED",
        "GATEWAY_TIMEOUT",
        "GATEWAY_ERROR",
        "PROCESSOR_DOWN",
        "NETWORK_REJECTED",
        "VELOCITY",
    }
)


# Recovery probability per (decline_code, strategy_kind) — for the mock
# gateway's "would this recovery have succeeded?" decision. Approximate.
RECOVERY_PROBABILITIES: dict[tuple[str, str], float] = {
    # FUNDS_INSUFFICIENT — best with payment link (customer-side action).
    ("FUNDS_INSUFFICIENT", "payment_link_nudge"): 0.55,
    ("FUNDS_INSUFFICIENT", "delayed_retry"):       0.18,
    ("FUNDS_INSUFFICIENT", "immediate_retry"):     0.05,

    # ISSUER_DO_NOT_HONOR — delayed retry helps; reroute helps more.
    ("ISSUER_DO_NOT_HONOR", "delayed_retry"):  0.42,
    ("ISSUER_DO_NOT_HONOR", "gateway_reroute"): 0.58,
    ("ISSUER_DO_NOT_HONOR", "immediate_retry"): 0.12,

    # GATEWAY_TIMEOUT / GATEWAY_ERROR — clear gateway issue, reroute wins.
    ("GATEWAY_TIMEOUT", "gateway_reroute"): 0.71,
    ("GATEWAY_TIMEOUT", "delayed_retry"):   0.48,
    ("GATEWAY_ERROR",   "gateway_reroute"): 0.74,
    ("GATEWAY_ERROR",   "delayed_retry"):   0.36,

    # PROCESSOR_DOWN — only reroute really helps.
    ("PROCESSOR_DOWN", "gateway_reroute"): 0.82,
    ("PROCESSOR_DOWN", "delayed_retry"):   0.20,

    # AUTH_3DS_REQUIRED — payment link / nudge for re-auth.
    ("AUTH_3DS_REQUIRED", "payment_link_nudge"): 0.62,

    # NETWORK_REJECTED — flaky; delayed retry sometimes works.
    ("NETWORK_REJECTED", "delayed_retry"): 0.33,
    ("NETWORK_REJECTED", "gateway_reroute"): 0.45,

    # VELOCITY — wait it out.
    ("VELOCITY", "delayed_retry"): 0.40,

    # CARD_EXPIRED / CARD_LOST_STOLEN / FRAUD_SUSPECTED / CVV_FAILED —
    # not recoverable by automated retry. Default 0.0 below.
}

DEFAULT_RECOVERY_PROBABILITY = 0.05


# Amount distribution — log-normal-ish in cents. Spread across realistic
# merchant ticket sizes.
AMOUNT_BUCKETS_CENTS: list[tuple[tuple[int, int], int]] = [
    # ((min, max), weight)
    ((100, 500),         5),    # $1-5
    ((500, 2000),        20),   # $5-20
    ((2000, 5000),       30),   # $20-50
    ((5000, 15000),      25),   # $50-150
    ((15000, 50000),     12),   # $150-500
    ((50000, 200000),    6),    # $500-2k
    ((200000, 1000000),  2),    # $2k-10k
]
assert sum(w for _, w in AMOUNT_BUCKETS_CENTS) == 100


# Gateways and issuers seen across the population.
GATEWAY_DISTRIBUTION: list[tuple[str, int]] = [
    ("stripe", 55),
    ("adyen",  25),
    ("braintree", 12),
    ("checkout", 8),
]
assert sum(w for _, w in GATEWAY_DISTRIBUTION) == 100

ISSUER_BINS: list[tuple[str, str]] = [
    # (bin, issuer_id)
    ("424242", "VISA_TEST"),
    ("411111", "VISA_GENERIC"),
    ("400000", "VISA_DEBIT"),
    ("555555", "MC_TEST"),
    ("520000", "MC_GENERIC"),
    ("378282", "AMEX_TEST"),
    ("601100", "DISCOVER_GENERIC"),
    ("352800", "JCB_GENERIC"),
]


@dataclass(frozen=True, slots=True)
class FailureSpec:
    """A single synthesized failure ready to be ingested by the API."""

    external_id: str
    amount_cents: int
    currency: str
    card_bin: str
    issuer_id: str
    gateway_provider: str
    decline_code_normalized: str
    decline_category: str
    is_soft_decline: bool


# -----------------------------------------------------------------------------
# Sampling helpers
# -----------------------------------------------------------------------------


def _weighted_choice(rng: random.Random, options: list[tuple]) -> tuple:
    total = sum(opt[-1] for opt in options)
    pick = rng.uniform(0, total)
    cumulative = 0.0
    for opt in options:
        cumulative += opt[-1]
        if pick <= cumulative:
            return opt
    return options[-1]


def sample_amount_cents(rng: random.Random) -> int:
    bucket, _ = _weighted_choice(rng, AMOUNT_BUCKETS_CENTS)
    lo, hi = bucket
    return rng.randint(lo, hi)


def sample_gateway(rng: random.Random) -> str:
    gw, _ = _weighted_choice(rng, GATEWAY_DISTRIBUTION)
    return gw


def sample_issuer(rng: random.Random) -> tuple[str, str]:
    """Returns (bin, issuer_id)."""
    return rng.choice(ISSUER_BINS)


def sample_decline(rng: random.Random) -> tuple[str, str, bool]:
    """Returns (code_normalized, category, is_soft_decline)."""
    code, category, _ = _weighted_choice(rng, DECLINE_CODE_WEIGHTS)
    is_soft = code in SOFT_DECLINE_CODES
    return code, category, is_soft


def recovery_probability(decline_code: str, strategy_kind: str) -> float:
    return RECOVERY_PROBABILITIES.get(
        (decline_code, strategy_kind), DEFAULT_RECOVERY_PROBABILITY
    )
