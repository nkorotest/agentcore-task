"""Tool errors.

ToolError is a problem with the request; it is returned to the agent as data and not retried.
Any other exception fails the invocation, so the gateway reports it and the caller can retry.
"""

from typing import Any


class ToolError(Exception):
    code = "TOOL_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message, "retryable": False}
        if self.details:
            error["details"] = self.details
        return {"error": error}


class InvalidParameterError(ToolError):
    code = "INVALID_PARAMETER"


class NotFoundError(ToolError):
    code = "NOT_FOUND"


class RefundExceedsOrderTotalError(ToolError):
    code = "REFUND_EXCEEDS_ORDER_TOTAL"


class IdempotencyConflictError(ToolError):
    code = "IDEMPOTENCY_CONFLICT"


class UpstreamServiceError(Exception):
    """A dependency failed in a way that may succeed on retry (for example an HTTP 5xx)."""
