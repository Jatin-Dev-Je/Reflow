"""Security settings — JWT auth + audit-log signing."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # JWT (FastAPI Users / API key tokens)
    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-in-production-this-is-not-safe"),
        description="HS256 signing key. MUST be overridden in any non-dev environment.",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_expires_minutes: int = Field(default=60, gt=0)
    jwt_refresh_expires_days: int = Field(default=30, gt=0)

    # Audit-log signing (Ed25519). See ADR-0002 + docs/architecture/overview.md §13.
    audit_signing_private_key_b64: SecretStr | None = Field(
        default=None,
        description="Base64-encoded Ed25519 private key (32 bytes). "
        "If None, a key is generated on startup — dev only.",
    )
    audit_signing_key_id: str = Field(
        default="local-v1",
        description="Identifier for the signing key. Switch to KMS key ARN in prod.",
    )
    audit_anchor_every_n_events: int = Field(
        default=100,
        ge=1,
        description="Compute & sign a Merkle anchor every N events.",
    )

    # Idempotency
    idempotency_required_methods: tuple[str, ...] = Field(
        default=("POST", "PUT", "PATCH", "DELETE"),
    )
    idempotency_ttl_hours: int = Field(default=24, gt=0)
