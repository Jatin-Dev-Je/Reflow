"""Inclusion-proof builder + verifier for the audit chain.

Given an event_id, we build a proof that the event is included in a signed
anchor. The proof is verifiable by anyone with the public key — no DB access
required.

Security properties:
    * The leaf hash is the event_hash recorded at write time, not recomputed
      now. If somebody tampered with the row, the leaf hash won't match the
      proof and verification fails.
    * The signature ties the root to the signing key id; a tamperer would have
      to forge an Ed25519 signature to swap the root.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reflow.core.exceptions import DomainError
from reflow.core.observability.logging import get_logger
from reflow.core.security.signing import Signature, verify
from reflow.core.types import EventId
from reflow.domain.audit import InclusionProof, ProofStep, ProofStepDirection
from reflow.infrastructure.audit_log.merkle import (
    inclusion_proof,
    verify_inclusion,
)
from reflow.infrastructure.persistence.models import ChainAnchorModel, EventModel

_logger = get_logger(__name__)


class EventNotAnchoredError(DomainError):
    error_code = "audit.event_not_anchored"
    http_status = 409


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of verifying an InclusionProof against the public key."""

    valid: bool
    reason: str | None = None


class AuditVerifier:
    """Build and verify audit-chain inclusion proofs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_proof(self, event_id: EventId) -> InclusionProof:
        """Build an inclusion proof for a single event.

        Raises:
            DomainError: event not found.
            EventNotAnchoredError: event exists but no anchor covers it yet.
        """
        event_row = await self._session.execute(
            select(
                EventModel.id,
                EventModel.global_sequence,
                EventModel.event_hash,
            ).where(EventModel.id == event_id)
        )
        event = event_row.one_or_none()
        if event is None:
            raise DomainError(f"Event {event_id} not found", context={"event_id": str(event_id)})

        anchor_row = await self._session.execute(
            select(ChainAnchorModel)
            .where(ChainAnchorModel.start_sequence <= event.global_sequence)
            .where(ChainAnchorModel.end_sequence >= event.global_sequence)
            .order_by(ChainAnchorModel.signed_at.desc())
            .limit(1)
        )
        anchor = anchor_row.scalar_one_or_none()
        if anchor is None:
            raise EventNotAnchoredError(
                f"Event {event_id} is not yet covered by a chain anchor",
                context={
                    "event_id": str(event_id),
                    "global_sequence": event.global_sequence,
                },
            )

        # Load leaves for the anchor range (ASC by global_sequence — same order
        # the anchor was computed from).
        leaves_stmt = (
            select(EventModel.global_sequence, EventModel.event_hash)
            .where(EventModel.global_sequence >= anchor.start_sequence)
            .where(EventModel.global_sequence <= anchor.end_sequence)
            .order_by(EventModel.global_sequence.asc())
        )
        rows = (await self._session.execute(leaves_stmt)).all()
        leaves = [r.event_hash for r in rows]
        sequences = [r.global_sequence for r in rows]
        target_index = sequences.index(event.global_sequence)

        path_raw = inclusion_proof(leaves, target_index)

        return InclusionProof(
            event_id=event_id,
            event_global_sequence=event.global_sequence,
            leaf_hash=event.event_hash,
            path=[
                ProofStep(sibling_hash=sibling, direction=ProofStepDirection(direction))
                for sibling, direction in path_raw
            ],
            anchor_id=str(anchor.id),
            anchor_start_sequence=anchor.start_sequence,
            anchor_end_sequence=anchor.end_sequence,
            merkle_root=anchor.merkle_root,
            signature=anchor.signature,
            signer_key_id=anchor.signer_key_id,
            signed_at=anchor.signed_at,
        )

    @staticmethod
    def verify_proof(proof: InclusionProof) -> VerificationResult:
        """Verify a proof. Pure — needs no DB access.

        Two checks:
            1. Inclusion: rebuilding the root from leaf_hash + path equals the
               proof's recorded root.
            2. Signature: the signature over the root verifies under the
               current signing key.
        """
        if not (proof.anchor_start_sequence <= proof.event_global_sequence <= proof.anchor_end_sequence):
            return VerificationResult(valid=False, reason="event sequence outside anchor range")

        merkle_ok = verify_inclusion(
            leaf_hex=proof.leaf_hash,
            path=[(step.sibling_hash, step.direction.value) for step in proof.path],
            expected_root_hex=proof.merkle_root,
        )
        if not merkle_ok:
            return VerificationResult(valid=False, reason="merkle inclusion failed")

        signature_ok = verify(
            proof.merkle_root.encode("ascii"),
            Signature(key_id=proof.signer_key_id, signature_hex=proof.signature),
        )
        if not signature_ok:
            return VerificationResult(valid=False, reason="signature verification failed")

        return VerificationResult(valid=True)
