"""Cancel tool calls once a request makes too many, or repeats the same call too often."""

import json
import logging
from collections import Counter
from typing import Any

from opentelemetry import trace
from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent, HookProvider, HookRegistry

logger = logging.getLogger(__name__)

STOP_MESSAGE = (
    "Loop guard: {reason} Do not call any more tools for this request. "
    "Answer the customer with the information you already have."
)


class LoopGuard(HookProvider):
    def __init__(self, *, max_tool_calls: int = 10, max_identical_calls: int = 3) -> None:
        self._max_tool_calls = max_tool_calls
        self._max_identical_calls = max_identical_calls
        self._seen_tool_use_ids: set[str] = set()
        self._calls_by_signature: Counter[str] = Counter()

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self._reset)
        registry.add_callback(BeforeToolCallEvent, self._check_tool_call)

    def _reset(self, event: BeforeInvocationEvent) -> None:
        self._seen_tool_use_ids.clear()
        self._calls_by_signature.clear()

    def _check_tool_call(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        if tool_use["toolUseId"] in self._seen_tool_use_ids:
            return  # a retry of a call that was already counted
        self._seen_tool_use_ids.add(tool_use["toolUseId"])

        signature = f"{tool_use['name']}:{json.dumps(tool_use.get('input'), sort_keys=True)}"
        self._calls_by_signature[signature] += 1
        total_calls = len(self._seen_tool_use_ids)

        if self._calls_by_signature[signature] > self._max_identical_calls:
            reason = (
                f"{tool_use['name']} was already called {self._max_identical_calls} times with "
                "the same input."
            )
        elif total_calls > self._max_tool_calls:
            reason = f"this request already made {self._max_tool_calls} tool calls."
        else:
            return

        logger.warning("Loop guard stopped tool %s: %s", tool_use["name"], reason)
        span = trace.get_current_span()
        span.set_attribute("loop_guard.triggered", True)
        span.add_event("loop_guard.stopped_tool_call", {"tool.name": tool_use["name"]})
        event.cancel_tool = STOP_MESSAGE.format(reason=reason)
