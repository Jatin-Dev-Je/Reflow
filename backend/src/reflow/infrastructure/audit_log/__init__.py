"""Audit log infrastructure — Merkle tree, chain anchoring, verification."""

from reflow.infrastructure.audit_log.chain import AnchorResult, ChainAnchorService
from reflow.infrastructure.audit_log.merkle import (
    inclusion_proof,
    merkle_root_bytes,
    merkle_root_hex,
    verify_inclusion,
)
from reflow.infrastructure.audit_log.verifier import (
    AuditVerifier,
    EventNotAnchoredError,
    VerificationResult,
)

__all__ = [
    "AnchorResult",
    "AuditVerifier",
    "ChainAnchorService",
    "EventNotAnchoredError",
    "VerificationResult",
    "inclusion_proof",
    "merkle_root_bytes",
    "merkle_root_hex",
    "verify_inclusion",
]
