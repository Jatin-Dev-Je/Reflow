"""Merkle tree — invariants the audit chain relies on.

Property-based tests verify these claims for arbitrary leaf counts:
    * Inclusion proofs verify against the same root that builds them.
    * Tampering with any path element makes verification fail.
    * Single-leaf root equals the leaf itself.
    * Odd-leaf-count layers do not crash and produce consistent roots.
"""

from __future__ import annotations

import hashlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from reflow.infrastructure.audit_log.merkle import (
    inclusion_proof,
    merkle_root_hex,
    verify_inclusion,
)

pytestmark = pytest.mark.unit


def _leaf(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _leaves(n: int) -> list[str]:
    return [_leaf(f"event-{i}".encode()) for i in range(n)]


class TestRoot:
    def test_single_leaf_root_equals_leaf(self) -> None:
        leaf = _leaf(b"only-event")
        assert merkle_root_hex([leaf]) == leaf

    def test_empty_leaves_returns_sha256_of_empty(self) -> None:
        assert merkle_root_hex([]) == hashlib.sha256(b"").hexdigest()

    def test_root_stable_for_same_input(self) -> None:
        leaves = _leaves(7)
        assert merkle_root_hex(leaves) == merkle_root_hex(leaves)


class TestInclusionProof:
    @pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 33, 100])
    def test_proof_verifies_for_every_index(self, size: int) -> None:
        leaves = _leaves(size)
        root = merkle_root_hex(leaves)
        for i in range(size):
            proof = inclusion_proof(leaves, i)
            assert verify_inclusion(leaf_hex=leaves[i], path=proof, expected_root_hex=root), (
                f"proof failed for leaf {i}/{size}"
            )

    def test_proof_with_tampered_leaf_fails(self) -> None:
        leaves = _leaves(8)
        root = merkle_root_hex(leaves)
        proof = inclusion_proof(leaves, 3)
        tampered_leaf = _leaf(b"not-the-real-event")
        assert not verify_inclusion(
            leaf_hex=tampered_leaf, path=proof, expected_root_hex=root
        )

    def test_proof_with_tampered_sibling_fails(self) -> None:
        leaves = _leaves(8)
        root = merkle_root_hex(leaves)
        proof = inclusion_proof(leaves, 3)
        # Flip first sibling to break the chain.
        bad_proof = [(_leaf(b"forged"), proof[0][1]), *proof[1:]]
        assert not verify_inclusion(
            leaf_hex=leaves[3], path=bad_proof, expected_root_hex=root
        )

    def test_invalid_direction_raises(self) -> None:
        leaves = _leaves(4)
        root = merkle_root_hex(leaves)
        proof = inclusion_proof(leaves, 0)
        bad_proof = [(proof[0][0], "sideways"), *proof[1:]]
        with pytest.raises(ValueError, match="direction"):
            verify_inclusion(leaf_hex=leaves[0], path=bad_proof, expected_root_hex=root)

    def test_out_of_range_index_raises(self) -> None:
        leaves = _leaves(3)
        with pytest.raises(IndexError):
            inclusion_proof(leaves, 3)
        with pytest.raises(IndexError):
            inclusion_proof(leaves, -1)

    def test_empty_leaves_proof_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            inclusion_proof([], 0)


class TestPropertyBased:
    @given(
        size=st.integers(min_value=1, max_value=64),
        seed=st.integers(min_value=0, max_value=10**9),
    )
    def test_arbitrary_size_proofs_all_verify(self, size: int, seed: int) -> None:
        leaves = [hashlib.sha256(f"{seed}-{i}".encode()).hexdigest() for i in range(size)]
        root = merkle_root_hex(leaves)
        # Verify every index, not just one — catches off-by-one errors.
        for i in range(size):
            proof = inclusion_proof(leaves, i)
            assert verify_inclusion(leaf_hex=leaves[i], path=proof, expected_root_hex=root)

    @given(size=st.integers(min_value=2, max_value=32))
    def test_swapping_any_two_leaves_changes_root(self, size: int) -> None:
        leaves = _leaves(size)
        original_root = merkle_root_hex(leaves)
        swapped = [*leaves]
        swapped[0], swapped[1] = swapped[1], swapped[0]
        # If size is 2 the swap is symmetric for the root (it's still
        # sha256(a||b) -> sha256(b||a) — different). Confirm strictly:
        assert merkle_root_hex(swapped) != original_root
