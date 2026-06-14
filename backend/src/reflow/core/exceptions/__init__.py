"""Exception hierarchy."""

from reflow.core.exceptions.base import ReflowError
from reflow.core.exceptions.domain import (
    AggregateNotFoundError,
    ApprovalRequiredError,
    ConcurrencyConflictError,
    DomainError,
    IdempotencyConflictError,
    InvariantViolationError,
    KillSwitchActiveError,
    PolicyDeniedError,
)
from reflow.core.exceptions.infrastructure import (
    CacheError,
    CircuitBreakerOpenError,
    DatabaseError,
    DependencyTimeoutError,
    EventBusError,
    GatewayError,
    InfrastructureError,
    LLMCostCapExceededError,
    LLMError,
    LLMValidationError,
)

__all__ = [
    "AggregateNotFoundError",
    "ApprovalRequiredError",
    "CacheError",
    "CircuitBreakerOpenError",
    "ConcurrencyConflictError",
    "DatabaseError",
    "DependencyTimeoutError",
    "DomainError",
    "EventBusError",
    "GatewayError",
    "IdempotencyConflictError",
    "InfrastructureError",
    "InvariantViolationError",
    "KillSwitchActiveError",
    "LLMCostCapExceededError",
    "LLMError",
    "LLMValidationError",
    "PolicyDeniedError",
    "ReflowError",
]
