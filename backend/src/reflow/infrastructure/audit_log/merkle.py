"""Merkle tree construction + inclusion-proof generation.

We rebuild the tree deterministically from the *leaves* (per-event hashes)
rather than caching a serialized tree, so the only persisted artifact is the
root in `audit.chain_anchors`. This means:

  * Producing a proof is O(N log N) for an N-leaf range — fine for the demo
    range (typically <=100 events per anchor). Production at scale should
    persist intermediate layers to make proofs O(log N).
  * Verification is O(log N) and stateless once you have the proof + root.

Odd-leaf-count layers duplicate the last element (Bitcoin-style) so an even
pair is always available.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Step:
    sibling_hash: bytes
    direction: str  # 'left' or 'right'


def _layer_pair(layer: list[bytes]) -> list[bytes]:
    if len(layer) % 2 == 1:
        layer = [*layer, layer[-1]]
    return [hashlib.sha256(layer[i] + layer[i + 1]).digest() for i in range(0, len(layer), 2)]


def merkle_root_bytes(leaves_hex: list[str]) -> bytes:
    """Compute the Merkle root for a list of hex leaf hashes."""
    if not leaves_hex:
        return hashlib.sha256(b"").digest()
    layer = [bytes.fromhex(h) for h in leaves_hex]
    while len(layer) > 1:
        layer = _layer_pair(layer)
    return layer[0]


def merkle_root_hex(leaves_hex: list[str]) -> str:
    return merkle_root_bytes(leaves_hex).hex()


def inclusion_proof(leaves_hex: list[str], target_index: int) -> list[tuple[str, str]]:
    """Generate an inclusion proof for `leaves_hex[target_index]`.

    Returns a list of (sibling_hex, direction) pairs from leaf to root.
    `direction` is the sibling's position relative to the running hash:
      'left'  -> sibling is on the left:  next = sha256(sibling || running)
      'right' -> sibling is on the right: next = sha256(running || sibling)
    """
    if not leaves_hex:
        raise ValueError("Cannot build inclusion proof for empty leaf list")
    if not 0 <= target_index < len(leaves_hex):
        raise IndexError(f"target_index {target_index} out of range [0, {len(leaves_hex)})")

    layer = [bytes.fromhex(h) for h in leaves_hex]
    idx = target_index
    proof: list[tuple[str, str]] = []

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer = [*layer, layer[-1]]

        if idx % 2 == 0:
            sibling = layer[idx + 1]
            proof.append((sibling.hex(), "right"))
        else:
            sibling = layer[idx - 1]
            proof.append((sibling.hex(), "left"))

        layer = [
            hashlib.sha256(layer[i] + layer[i + 1]).digest() for i in range(0, len(layer), 2)
        ]
        idx //= 2

    return proof


def verify_inclusion(
    *,
    leaf_hex: str,
    path: list[tuple[str, str]],
    expected_root_hex: str,
) -> bool:
    """Verify an inclusion proof. Pure function — no I/O."""
    running = bytes.fromhex(leaf_hex)
    for sibling_hex, direction in path:
        sibling = bytes.fromhex(sibling_hex)
        if direction == "left":
            running = hashlib.sha256(sibling + running).digest()
        elif direction == "right":
            running = hashlib.sha256(running + sibling).digest()
        else:
            raise ValueError(f"Invalid proof step direction: {direction!r}")
    return running.hex() == expected_root_hex
