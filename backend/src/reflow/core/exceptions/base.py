"""Exception hierarchy base.

Two top-level branches:
    * ReflowError              — base. All app exceptions inherit.
        * DomainError          — business-rule violation (caller may recover).
        * InfrastructureError  — external/system failure (caller usually retries).

Each exception carries an `error_code` so API responses and audit logs can
identify them without parsing free-text messages.
"""

from __future__ import annotations

from typing import Any


class ReflowError(Exception):
    """Base class for every exception thrown by Reflow code."""

    error_code: str = "reflow.error"
    http_status: int = 500

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }
