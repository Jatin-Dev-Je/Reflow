"""Result type — explicit success/failure carriage.

Used at boundaries where exceptions would obscure flow (e.g., command handlers
that need to distinguish "command rejected" from "infrastructure exploded").
Inside the domain layer, prefer raising typed exceptions. Use Result at the
edges where the caller wants to react, not crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True


Result = Ok[T] | Err[E]
