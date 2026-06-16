"""HTTP schemas for system endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SystemInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    env: str
    is_production: bool


class AuditPublicKey(BaseModel):
    """Public key clients use to verify InclusionProofs offline."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str = "ed25519"
    public_key_b64: str
    key_id: str
