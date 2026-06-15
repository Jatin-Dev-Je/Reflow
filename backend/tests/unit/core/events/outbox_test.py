"""Outbox relay — pure-function tests.

The leader-elected loop + Redis publish path is covered by an integration
test (requires testcontainers Postgres + Redis). Here we cover the
deterministic helpers: destination parsing + backoff math.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reflow.core.events.outbox import (
    BACKOFF_JITTER_FRACTION,
    _backoff_until,
    _parse_destination,
)

pytestmark = pytest.mark.unit


class TestParseDestination:
    def test_standard_redis_stream_destination(self) -> None:
        kind, name = _parse_destination("redis-stream:transactions")
        assert kind == "redis-stream"
        assert name == "transactions"

    def test_destination_without_colon(self) -> None:
        kind, name = _parse_destination("redis-stream")
        assert kind == "redis-stream"
        assert name == ""

    def test_destination_with_multiple_colons_keeps_remainder(self) -> None:
        kind, name = _parse_destination("redis-stream:tenant-123:transactions")
        assert kind == "redis-stream"
        assert name == "tenant-123:transactions"


class TestBackoff:
    def test_attempt_zero_yields_short_wait(self) -> None:
        # base = 1s, jitter +/- 25% => wait <= 1.25s above now
        now = datetime.now(UTC)
        next_at = _backoff_until(0)
        assert next_at > now
        assert (next_at - now).total_seconds() <= 2.0

    def test_each_attempt_grows_exponentially(self) -> None:
        # Sample many attempts and assert average grows.
        from statistics import mean

        diffs: list[float] = []
        for attempt in range(0, 6):
            samples = []
            for _ in range(20):
                samples.append((_backoff_until(attempt) - datetime.now(UTC)).total_seconds())
            diffs.append(mean(samples))

        for i in range(len(diffs) - 1):
            assert diffs[i] < diffs[i + 1], (
                f"backoff did not grow at attempt {i}: {diffs[i]:.2f} -> {diffs[i + 1]:.2f}"
            )

    def test_attempts_clamped_around_5_minutes_max(self) -> None:
        # Very large attempt should still produce a sane bounded delay (<=6 min).
        next_at = _backoff_until(50)
        delta = (next_at - datetime.now(UTC)).total_seconds()
        assert 0 < delta <= 360.0

    def test_jitter_keeps_minimum_above_one_second(self) -> None:
        # Even at attempt 0 with negative jitter, the minimum cap should kick in.
        now = datetime.now(UTC)
        for _ in range(50):
            next_at = _backoff_until(0)
            assert (next_at - now).total_seconds() >= 0.9  # tiny tolerance for clock skew

    def test_backoff_jitter_constant_in_expected_range(self) -> None:
        assert 0 < BACKOFF_JITTER_FRACTION < 1
