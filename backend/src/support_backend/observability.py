"""Logging and the handler wrapper shared by all tools."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from .errors import ToolError

logger = logging.getLogger("support_backend")
logger.setLevel(logging.INFO)

ToolImplementation = Callable[[dict[str, Any]], dict[str, Any]]
LambdaHandler = Callable[[Any, Any], dict[str, Any]]

# Keys AgentCore Gateway puts in the Lambda client context, mapped to log field names.
_GATEWAY_CONTEXT_FIELDS = {
    "bedrockAgentCoreToolName": "gateway_tool_name",
    "bedrockAgentCoreGatewayId": "gateway_id",
    "bedrockAgentCoreTargetId": "gateway_target_id",
    "bedrockAgentCoreMcpMessageId": "mcp_message_id",
    "bedrockAgentCoreAwsRequestId": "gateway_request_id",
}


def gateway_metadata(context: Any) -> dict[str, str]:
    client_context = getattr(context, "client_context", None)
    custom = getattr(client_context, "custom", None) or {}
    return {
        field: str(custom[key]) for key, field in _GATEWAY_CONTEXT_FIELDS.items() if key in custom
    }


def tool_handler(tool_name: str) -> Callable[[ToolImplementation], LambdaHandler]:
    """Turn a tool implementation into a Lambda handler with logging and the error contract.

    ToolError -> structured {"error": {...}} result for the agent.
    Any other exception -> logged and re-raised, so the invocation fails visibly.
    """

    def decorator(implementation: ToolImplementation) -> LambdaHandler:
        @functools.wraps(implementation)
        def handler(event: Any, context: Any) -> dict[str, Any]:
            arguments = event if isinstance(event, dict) else {}
            log_fields = {"tool": tool_name, **gateway_metadata(context)}
            logger.info("Tool invoked", extra={**log_fields, "arguments": arguments})
            try:
                result = implementation(arguments)
            except ToolError as error:
                logger.warning(
                    "Tool rejected the request",
                    extra={**log_fields, "error_code": error.code, "error_message": error.message},
                )
                return error.to_response()
            except Exception:
                logger.exception("Tool failed", extra=log_fields)
                raise
            logger.info("Tool succeeded", extra=log_fields)
            return result

        return handler

    return decorator
