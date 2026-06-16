"""Password hashing — argon2id via passlib.

Why argon2id:
    * Resistant to GPU + side-channel attacks
    * Tunable memory + time cost
    * OWASP-recommended for new applications

All hashing is delegated to passlib so we get versioned hashing strings
(prefix indicates algorithm + params); upgrades are detected via
`.needs_update()`.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("password must be non-empty")
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return _pwd.verify(plain, hashed)
    except Exception:  # noqa: BLE001 — never crash on malformed hash
        return False


def needs_rehash(hashed: str) -> bool:
    return _pwd.needs_update(hashed)
