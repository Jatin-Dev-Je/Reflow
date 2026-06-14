"""Domain event infrastructure: base class, registry, upcasters."""

from reflow.core.events.event import DomainEvent, EventMetadata
from reflow.core.events.registry import (
    get_event_class,
    known_event_types,
    register_event,
    register_upcaster,
    upcast,
)

__all__ = [
    "DomainEvent",
    "EventMetadata",
    "get_event_class",
    "known_event_types",
    "register_event",
    "register_upcaster",
    "upcast",
]
