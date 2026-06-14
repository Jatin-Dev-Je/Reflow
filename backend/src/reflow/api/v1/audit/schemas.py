"""HTTP schemas for audit endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    global_sequence: int
    tenant_id: UUID
    stream_id: str
    stream_type: str
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    metadata: dict[str, Any]
    occurred_at: datetime
    recorded_at: datetime
    previous_hash: str | None
    event_hash: str


class ChainAnchorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    start_sequence: int
    end_sequence: int
    event_count: int
    merkle_root: str
    signature: str
    signer_key_id: str
    signed_at: datetime


class VerifyResponse(BaseModel):
    """Result of a verify/{event_id} call.

    `valid=true` means: the leaf hash recorded in the event row hashes up to
    the Merkle root that was signed at anchor time, and the signature over
    that root is valid under the signer's key.
    """

    valid: bool
    reason: str | None = None
    proof: dict[str, Any] = Field(
        description="The full inclusion proof — clients can independently re-verify."
    )
