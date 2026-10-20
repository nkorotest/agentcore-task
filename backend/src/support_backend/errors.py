"""Error contract shared by all tools.

ToolError subclasses are problems with the request itself (bad input, unknown IDs, business-rule
violations). They are returned to the agent as a structured result so the model can explain or
correct them, and retrying the same call would not help.

Any other exception, including UpstreamServiceError, fails the Lambda invocation. AgentCore Gateway
reports it as a tool error and the caller may retry with backoff.
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
