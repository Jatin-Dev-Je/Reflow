"""System endpoints — info, audit public key."""

from __future__ import annotations

from fastapi import APIRouter

from reflow import __version__
from reflow.api.deps import SettingsDep
from reflow.api.v1.system.schemas import AuditPublicKey, SystemInfo
from reflow.core.security.signing import public_key_b64

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/info",
    response_model=SystemInfo,
    summary="Build + environment metadata",
)
async def system_info(settings: SettingsDep) -> SystemInfo:
    return SystemInfo(
        name=settings.name,
        version=__version__,
        env=settings.env.value,
        is_production=settings.is_production,
    )


@router.get(
    "/audit-key",
    response_model=AuditPublicKey,
    summary="Ed25519 public key for offline verification of audit proofs",
)
async def audit_key(settings: SettingsDep) -> AuditPublicKey:
    return AuditPublicKey(
        algorithm="ed25519",
        public_key_b64=public_key_b64(),
        key_id=settings.security.audit_signing_key_id,
    )
