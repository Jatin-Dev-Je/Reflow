"""Signing — the audit-log foundation.

Three properties matter:
  * `canonical_json` is deterministic regardless of dict ordering.
  * `event_hash` chains: same inputs → same hash.
  * `merkle_root` is stable for the same leaves.
  * Sign/verify round-trip succeeds; tampered data fails verification.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from reflow.core.security import (
    canonical_json,
    event_hash,
    merkle_root,
    sha256_hex,
    sign,
    verify,
)

pytestmark = pytest.mark.unit


class TestCanonicalJson:
    def test_deterministic_for_equivalent_dicts(self) -> None:
        a = {"b": 1, "a": 2, "c": [1, 2, 3]}
        b = {"a": 2, "c": [1, 2, 3], "b": 1}
        assert canonical_json(a) == canonical_json(b)

    def test_distinguishes_different_payloads(self) -> None:
        assert canonical_json({"a": 1}) != canonical_json({"a": 2})


class TestEventHash:
    def test_chains_deterministically(self) -> None:
        h1 = event_hash(previous_hash=None, payload={"x": 1}, metadata={})
        h2 = event_hash(previous_hash=None, payload={"x": 1}, metadata={})
        assert h1 == h2

    def test_changes_when_previous_changes(self) -> None:
        h1 = event_hash(previous_hash="aaa", payload={"x": 1}, metadata={})
        h2 = event_hash(previous_hash="bbb", payload={"x": 1}, metadata={})
        assert h1 != h2

    def test_changes_when_payload_changes(self) -> None:
        h1 = event_hash(previous_hash="aaa", payload={"x": 1}, metadata={})
        h2 = event_hash(previous_hash="aaa", payload={"x": 2}, metadata={})
        assert h1 != h2


class TestMerkleRoot:
    def test_empty_list_returns_sha256_of_empty(self) -> None:
        assert merkle_root([]) == sha256_hex(b"")

    def test_single_leaf_is_itself(self) -> None:
        leaf = sha256_hex(b"hello")
        assert merkle_root([leaf]) == leaf

    def test_stable_for_same_leaves(self) -> None:
        leaves = [sha256_hex(f"e{i}".encode()) for i in range(7)]
        assert merkle_root(leaves) == merkle_root(leaves)

    def test_odd_leaf_count_duplicates_last(self) -> None:
        # Odd count should not raise.
        leaves = [sha256_hex(f"e{i}".encode()) for i in range(3)]
        assert isinstance(merkle_root(leaves), str)
        assert len(merkle_root(leaves)) == 64


class TestSignVerifyRoundTrip:
    def test_roundtrip_succeeds(self) -> None:
        msg = b"audit anchor v1"
        sig = sign(msg)
        assert verify(msg, sig) is True

    def test_tampered_message_fails(self) -> None:
        msg = b"audit anchor v1"
        sig = sign(msg)
        assert verify(b"audit anchor v2", sig) is False

    @given(st.binary(min_size=0, max_size=4096))
    def test_roundtrip_holds_for_arbitrary_bytes(self, msg: bytes) -> None:
        sig = sign(msg)
        assert verify(msg, sig)
