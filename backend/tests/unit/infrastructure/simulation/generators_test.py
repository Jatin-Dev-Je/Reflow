"""Simulation generators + distributions — reproducibility and shape."""

from __future__ import annotations

import pytest

from reflow.infrastructure.simulation.distributions import (
    DECLINE_CODE_WEIGHTS,
    GATEWAY_DISTRIBUTION,
    AMOUNT_BUCKETS_CENTS,
    SOFT_DECLINE_CODES,
    recovery_probability,
)
from reflow.infrastructure.simulation.generators.transaction import generate_failures

pytestmark = pytest.mark.unit


class TestDistributionInvariants:
    def test_decline_weights_sum_to_100(self) -> None:
        assert sum(w for _, _, w in DECLINE_CODE_WEIGHTS) == 100

    def test_amount_weights_sum_to_100(self) -> None:
        assert sum(w for _, w in AMOUNT_BUCKETS_CENTS) == 100

    def test_gateway_weights_sum_to_100(self) -> None:
        assert sum(w for _, w in GATEWAY_DISTRIBUTION) == 100

    def test_soft_decline_codes_subset_of_taxonomy(self) -> None:
        taxonomy = {code for code, _, _ in DECLINE_CODE_WEIGHTS}
        assert SOFT_DECLINE_CODES.issubset(taxonomy)


class TestRecoveryProbability:
    def test_known_combo_returns_specific_probability(self) -> None:
        assert recovery_probability("PROCESSOR_DOWN", "gateway_reroute") == 0.82

    def test_unknown_combo_returns_default(self) -> None:
        p = recovery_probability("UNKNOWN_CODE", "unknown_strategy")
        assert p == 0.05

    def test_probabilities_in_valid_range(self) -> None:
        from reflow.infrastructure.simulation.distributions import RECOVERY_PROBABILITIES
        for p in RECOVERY_PROBABILITIES.values():
            assert 0.0 <= p <= 1.0


class TestGeneratorReproducibility:
    def test_same_seed_produces_identical_stream(self) -> None:
        a = list(generate_failures(count=200, seed=42))
        b = list(generate_failures(count=200, seed=42))
        assert a == b

    def test_different_seeds_diverge(self) -> None:
        a = list(generate_failures(count=200, seed=42))
        b = list(generate_failures(count=200, seed=99))
        # Compare first 10 — should differ in at least 5 fields.
        diffs = sum(
            1 for x, y in zip(a[:10], b[:10], strict=True) if x != y
        )
        assert diffs >= 5

    def test_count_is_honoured(self) -> None:
        items = list(generate_failures(count=137, seed=1))
        assert len(items) == 137

    def test_distribution_roughly_matches_at_scale(self) -> None:
        """At 10k samples, the empirical proportion should be within ~3%
        of the configured weight for the top codes."""
        items = list(generate_failures(count=10_000, seed=7))
        from collections import Counter

        counts = Counter(x.decline_code_normalized for x in items)
        total = sum(counts.values())

        # FUNDS_INSUFFICIENT is configured at 22%.
        funds_share = counts.get("FUNDS_INSUFFICIENT", 0) / total
        assert 0.18 <= funds_share <= 0.26, f"FUNDS_INSUFFICIENT share = {funds_share:.3f}"

    def test_external_ids_are_unique(self) -> None:
        items = list(generate_failures(count=1000, seed=1))
        ids = {x.external_id for x in items}
        assert len(ids) == 1000

    def test_amounts_positive_and_bounded(self) -> None:
        items = list(generate_failures(count=500, seed=1))
        for x in items:
            assert 100 <= x.amount_cents <= 1_000_000
