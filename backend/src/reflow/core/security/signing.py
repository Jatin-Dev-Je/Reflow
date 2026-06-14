"""Cryptographic signing for the audit log.

We use Ed25519 because:
  * Deterministic signatures (no nonce reuse risk)
  * Small keys (32 bytes) and signatures (64 bytes)
  * Fast and constant-time in nacl
  * Recognised by every auditor / regulator who's seen real crypto

The private key is loaded from `SECURITY_AUDIT_SIGNING_PRIVATE_KEY_B64` in env.
If absent — dev only — we generate an ephemeral key and warn loudly.  In prod
this MUST come from a KMS or vault; the API is shape-compatible so the swap is
mechanical.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

import orjson
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from reflow.core.config import SecuritySettings, get_settings
from reflow.core.observability.logging import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Signature:
    key_id: str
    signature_hex: str

    def to_dict(self) -> dict[str, str]:
        return {"key_id": self.key_id, "signature": self.signature_hex}


def canonical_json(payload: object) -> bytes:
    """Deterministic JSON serialization.

    orjson with OPT_SORT_KEYS gives the same bytes for the same dict content
    regardless of insertion order — required so the hash of an event payload
    is reproducible.
    """
    return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS | orjson.OPT_NAIVE_UTC)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def event_hash(*, previous_hash: str | None, payload: object, metadata: object) -> str:
    """Compute the chained hash for an event.

    Layout:
        sha256( previous_hash || canonical_json(payload) || canonical_json(metadata) )
    """
    h = hashlib.sha256()
    if previous_hash:
        h.update(previous_hash.encode("ascii"))
    h.update(canonical_json(payload))
    h.update(canonical_json(metadata))
    return h.hexdigest()


def merkle_root(hashes: list[str]) -> str:
    """Compute a binary Merkle root over a list of hex hashes.

    Duplicates the last node if the level has an odd count (Bitcoin-style).
    """
    if not hashes:
        return sha256_hex(b"")
    layer = [bytes.fromhex(h) for h in hashes]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [hashlib.sha256(layer[i] + layer[i + 1]).digest() for i in range(0, len(layer), 2)]
    return layer[0].hex()


# -----------------------------------------------------------------------------
# Signer — lazy-loaded singleton keyed by settings.
# -----------------------------------------------------------------------------

_signing_key: SigningKey | None = None
_verify_key: VerifyKey | None = None
_key_id: str = "local-v1"


def _load_keys(settings: SecuritySettings) -> tuple[SigningKey, VerifyKey, str]:
    if settings.audit_signing_private_key_b64 is not None:
        raw = base64.b64decode(settings.audit_signing_private_key_b64.get_secret_value())
        if len(raw) != 32:
            raise ValueError("Ed25519 private key must be 32 bytes (base64-decoded).")
        sk = SigningKey(raw)
    else:
        # Dev-only: generate ephemeral key. Loud warning so this isn't accidentally used in prod.
        _logger.warning(
            "audit.signing.ephemeral_key",
            message="No AUDIT_SIGNING_PRIVATE_KEY_B64 configured — generated ephemeral key. "
            "Audit chain anchors cannot be verified across restarts. Dev only.",
        )
        sk = SigningKey.generate()
    return sk, sk.verify_key, settings.audit_signing_key_id


def _ensure_signer() -> tuple[SigningKey, VerifyKey, str]:
    global _signing_key, _verify_key, _key_id
    if _signing_key is None or _verify_key is None:
        _signing_key, _verify_key, _key_id = _load_keys(get_settings().security)
    return _signing_key, _verify_key, _key_id


def sign(message: bytes) -> Signature:
    sk, _, key_id = _ensure_signer()
    sig = sk.sign(message).signature
    return Signature(key_id=key_id, signature_hex=sig.hex())


def verify(message: bytes, signature: Signature, verify_key: VerifyKey | None = None) -> bool:
    if verify_key is None:
        _, verify_key, _ = _ensure_signer()
    try:
        verify_key.verify(message, bytes.fromhex(signature.signature_hex))
        return True
    except BadSignatureError:
        return False


def public_key_b64() -> str:
    _, vk, _ = _ensure_signer()
    return base64.b64encode(bytes(vk)).decode("ascii")
