"""Retry transient tool failures with exponential backoff and jitter.

A retry re-sends the same call, including its idempotency key. Gateway target failures
(isError) and transport errors are retried; business errors and policy denials are not.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

from opentelemetry import trace
from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

logger = logging.getLogger(__name__)

_FINAL_FAILURE_MARKERS = ("tool execution denied",)
_TRANSIENT_FAILURE_MARKERS = (
    "timed out",
    "timeout",
    "retry later",
    "temporarily unavailable",
    "too many requests",
    "throttl",
    "connection",
)


def is_transient_failure(result: dict[str, Any]) -> bool:
    if result.get("status") != "error":
        return False
    text = " ".join(item.get("text", "") for item in result.get("content", [])).lower()
    if any(marker in text for marker in _FINAL_FAILURE_MARKERS):
        return False
    return result.get("isError") is True or any(
        marker in text for marker in _TRANSIENT_FAILURE_MARKERS
    )


class ToolRetry(HookProvider):
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 4.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._max_delay_seconds = max_delay_seconds
        self._sleep = sleep
        self._attempts: dict[str, int] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._retry_transient_failure)

    def backoff_delay(self, attempt: int) -> float:
        """Full jitter: a random delay up to base * 2^(attempt - 1), capped at max_delay."""
        ceiling = min(self._max_delay_seconds, self._base_delay_seconds * 2 ** (attempt - 1))
        return random.uniform(0, ceiling)

    async def _retry_transient_failure(self, event: AfterToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        if event.cancel_message is not None or not is_transient_failure(event.result):
            self._attempts.pop(tool_use_id, None)
            return

        attempt = self._attempts.get(tool_use_id, 1)
        tool_name = event.tool_use["name"]
        if attempt >= self._max_attempts:
            logger.error(
                "Tool %s failed after %d attempts; giving up",
                tool_name,
                attempt,
                extra={"tool_use_id": tool_use_id},
            )
            self._attempts.pop(tool_use_id, None)
            return

        delay = self.backoff_delay(attempt)
        logger.warning(
            "Transient failure of tool %s (attempt %d of %d); retrying in %.2fs",
            tool_name,
            attempt,
            self._max_attempts,
            delay,
            extra={"tool_use_id": tool_use_id},
        )
        span = trace.get_current_span()
        span.set_attribute("tool.retry.attempt", attempt)
        span.add_event("tool.retry", {"tool.name": tool_name, "retry.delay_seconds": delay})

        await self._sleep(delay)
        self._attempts[tool_use_id] = attempt + 1
        event.retry = True
