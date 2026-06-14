"""Audit value objects — Citation, Evidence, Provenance, Inclusion proof.

Citations are first-class. Every agent decision MUST carry at least one
citation pointing back into the data layer (an event_id, a snapshot, a
recovery_pattern row, a health_snapshot bucket).

A citation answers: "Where did this claim come from? Can I verify it?"
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from reflow.core.types import EventId, TenantId


class EvidenceType(StrEnum):
    HISTORICAL_RECOVERY = "historical_recovery"
    GATEWAY_HEALTH = "gateway_health"
    ISSUER_HEALTH = "issuer_health"
    PATTERN_MATCH = "pattern_match"
    SIMILAR_FAILURE = "similar_failure"
    RULE_MATCH = "rule_match"
    EXTERNAL_SIGNAL = "external_signal"


class CitationSource(BaseModel):
    """Where the evidence came from. Replayable — given (source_table,
    source_query) we can re-execute the lookup and re-verify the data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_table: str = Field(
        description="Schema-qualified table or matview, e.g. 'intel.recovery_patterns'."
    )
    source_query: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured query parameters used to fetch the evidence. "
        "Excludes secret-bearing fields; safe to log.",
    )


class Citation(BaseModel):
    """A single [N] citation backing a claim.

    The `observation` is the human-readable summary ('Success rate dropped
    97%→63% in last 15 min'); `data` is the structured measurement; `weight`
    is the contribution to the parent claim's confidence (sum-to-one across
    citations is *not* required — citations can be qualitatively additive).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=1, description="The [N] index displayed in the UI.")
    evidence_type: EvidenceType
    source: CitationSource
    observation: str = Field(min_length=1, max_length=1024)
    data: dict[str, Any] = Field(default_factory=dict)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_at: datetime


class Provenance(BaseModel):
    """The full causal chain for an artifact (decision, recommendation, action).

    A Provenance points at the events that led to it, the agent runs that
    produced it, and the citations that ground its claims. This is what the
    Trust View renders.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: str
    artifact_type: str
    tenant_id: TenantId
    causation_event_ids: list[EventId] = Field(default_factory=list)
    agent_run_ids: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime


# -----------------------------------------------------------------------------
# Inclusion proof — Merkle path for a single event up to an anchor.
# -----------------------------------------------------------------------------


class ProofStepDirection(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class ProofStep(BaseModel):
    """One step in a Merkle inclusion proof.

    `sibling_hash` is hashed with the running hash according to `direction`:
        direction=LEFT  -> next = sha256(sibling_hash || running)
        direction=RIGHT -> next = sha256(running || sibling_hash)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sibling_hash: str = Field(min_length=64, max_length=64)
    direction: ProofStepDirection


class InclusionProof(BaseModel):
    """A verifiable proof that a single event is part of a signed anchor.

    Verification steps:
        1. Re-hash the event payload + metadata + previous_hash and compare
           to `leaf_hash`.
        2. Walk `path`, combining each sibling per its direction.
        3. The final value must equal `merkle_root`.
        4. Verify `signature` over `merkle_root` using `signer_key_id`'s
           public key.
        5. Confirm `event_global_sequence` ∈ [anchor.start_sequence,
           anchor.end_sequence].
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: EventId
    event_global_sequence: int = Field(gt=0)
    leaf_hash: str = Field(min_length=64, max_length=64)
    path: list[ProofStep]

    anchor_id: str
    anchor_start_sequence: int = Field(gt=0)
    anchor_end_sequence: int = Field(gt=0)
    merkle_root: str = Field(min_length=64, max_length=64)
    signature: str
    signer_key_id: str
    signed_at: datetime
