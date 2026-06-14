"""Domain exceptions — business-rule violations.

Raised when an operation is rejected because the request violates a domain
invariant or policy. These translate to 4xx responses at the API edge.
"""

from __future__ import annotations

from reflow.core.exceptions.base import ReflowError


class DomainError(ReflowError):
    error_code = "domain.error"
    http_status = 400


class AggregateNotFoundError(DomainError):
    error_code = "domain.aggregate_not_found"
    http_status = 404


class ConcurrencyConflictError(DomainError):
    """Optimistic concurrency conflict on event-sourced stream."""

    error_code = "domain.concurrency_conflict"
    http_status = 409


class InvariantViolationError(DomainError):
    """Aggregate refused a command because it would break an invariant."""

    error_code = "domain.invariant_violation"
    http_status = 422


class IdempotencyConflictError(DomainError):
    """Same idempotency key used with a different payload."""

    error_code = "domain.idempotency_conflict"
    http_status = 409


class PolicyDeniedError(DomainError):
    error_code = "domain.policy_denied"
    http_status = 403


class KillSwitchActiveError(DomainError):
    error_code = "domain.killswitch_active"
    http_status = 503


class ApprovalRequiredError(DomainError):
    """Operation requires HITL approval before proceeding."""

    error_code = "domain.approval_required"
    http_status = 202
