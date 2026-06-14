"""Infrastructure exceptions — external/system failures.

Raised when an external dependency or systems-level operation fails. These
typically translate to 5xx responses, drive retries, and trip circuit breakers.
"""

from __future__ import annotations

from reflow.core.exceptions.base import ReflowError


class InfrastructureError(ReflowError):
    error_code = "infrastructure.error"
    http_status = 500


class DatabaseError(InfrastructureError):
    error_code = "infrastructure.database_error"


class CacheError(InfrastructureError):
    error_code = "infrastructure.cache_error"


class EventBusError(InfrastructureError):
    error_code = "infrastructure.event_bus_error"


class DependencyTimeoutError(InfrastructureError):
    error_code = "infrastructure.dependency_timeout"
    http_status = 504


class CircuitBreakerOpenError(InfrastructureError):
    error_code = "infrastructure.circuit_breaker_open"
    http_status = 503


class GatewayError(InfrastructureError):
    error_code = "infrastructure.gateway_error"
    http_status = 502


class LLMError(InfrastructureError):
    error_code = "infrastructure.llm_error"


class LLMValidationError(LLMError):
    """LLM produced output that failed schema validation after all repair attempts."""

    error_code = "infrastructure.llm_validation_failed"


class LLMCostCapExceededError(LLMError):
    error_code = "infrastructure.llm_cost_cap_exceeded"
    http_status = 402
