"""Event type registry — name <-> class.

Used at load time to materialise events from JSONB rows back into typed
Python objects. Lookup by `(event_type, schema_version)` to support upcasters
when payloads evolve.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflow.core.events.event import DomainEvent


_registry: dict[tuple[str, int], type[DomainEvent]] = {}
_upcasters: dict[tuple[str, int], "Upcaster"] = {}

# Upcaster: takes an older payload dict, returns a new one of the next schema_version.
type Upcaster = "callable[[dict], dict]"


def register_event(event_cls: type[DomainEvent]) -> type[DomainEvent]:
    """Class decorator: register an event class so it can be reconstructed by type."""
    key = (event_cls.event_type, event_cls.schema_version)
    if key in _registry:
        raise RuntimeError(
            f"Event already registered: {event_cls.event_type} v{event_cls.schema_version}"
        )
    _registry[key] = event_cls
    return event_cls


def register_upcaster(*, event_type: str, from_version: int, upcaster: Upcaster) -> None:
    """Register a function that bumps a payload from N -> N+1 for an event_type."""
    _upcasters[(event_type, from_version)] = upcaster


def get_event_class(event_type: str, schema_version: int) -> type[DomainEvent] | None:
    return _registry.get((event_type, schema_version))


def upcast(event_type: str, payload: dict, from_version: int, to_version: int) -> dict:
    """Chain upcasters until payload is at the target schema_version."""
    current_version = from_version
    current = payload
    while current_version < to_version:
        upcaster = _upcasters.get((event_type, current_version))
        if upcaster is None:
            raise RuntimeError(
                f"No upcaster for {event_type} v{current_version} -> v{current_version + 1}"
            )
        current = upcaster(current)
        current_version += 1
    return current


def known_event_types() -> list[tuple[str, int]]:
    return list(_registry.keys())
