import asyncio

import pytest
from strands.hooks import AfterToolCallEvent, HookRegistry

from reliability import tool_retry
from reliability.tool_retry import ToolRetry, is_transient_failure

GATEWAY_TARGET_FAILURE = {
    "status": "error",
    "isError": True,
    "content": [{"text": "An internal error occurred. Please retry later."}],
}
POLICY_DENIAL = {
    "status": "error",
    "content": [
        {
            "text": "Tool execution failed: Tool Execution Denied: Tool call not allowed due to "
            "policy enforcement [No policy applies to the request (denied by default).]"
        }
    ],
}
TRANSPORT_TIMEOUT = {
    "status": "error",
    "content": [{"text": "Tool execution failed: Timed out while waiting for response"}],
}
BUSINESS_ERROR = {
    "status": "success",
    "content": [{"text": '{"error": {"code": "NOT_FOUND", "retryable": false}}'}],
}


class FakeSleep:
    def __init__(self):
        self.delays = []

    async def __call__(self, seconds):
        self.delays.append(seconds)


def after_tool_call(result, *, tool_use_id="tool-1", cancel_message=None):
    return AfterToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={
            "toolUseId": tool_use_id,
            "name": "RefundsTarget___refund_customer",
            "input": {"order_id": "123", "amount_cents": 2500, "idempotency_key": "operation-123"},
        },
        invocation_state={},
        result={"toolUseId": tool_use_id, **result},
        cancel_message=cancel_message,
    )


def run_hook(hook, event):
    registry = HookRegistry()
    hook.register_hooks(registry)
    event, _ = asyncio.run(registry.invoke_callbacks_async(event))
    return event


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (GATEWAY_TARGET_FAILURE, True),
        (TRANSPORT_TIMEOUT, True),
        (POLICY_DENIAL, False),
        (BUSINESS_ERROR, False),
        ({"status": "success", "content": [{"text": "{}"}]}, False),
    ],
)
def test_is_transient_failure(result, expected):
    assert is_transient_failure(result) is expected


def test_transient_failure_is_retried_after_a_backoff_delay():
    sleep = FakeSleep()
    event = run_hook(ToolRetry(sleep=sleep), after_tool_call(GATEWAY_TARGET_FAILURE))

    assert event.retry is True
    assert len(sleep.delays) == 1
    assert 0 <= sleep.delays[0] <= 0.5


def test_retries_stop_after_max_attempts():
    sleep = FakeSleep()
    hook = ToolRetry(max_attempts=3, sleep=sleep)

    decisions = [run_hook(hook, after_tool_call(GATEWAY_TARGET_FAILURE)).retry for _ in range(3)]

    assert decisions == [True, True, False]
    assert len(sleep.delays) == 2


@pytest.mark.parametrize("result", [POLICY_DENIAL, BUSINESS_ERROR])
def test_final_outcomes_are_not_retried(result):
    sleep = FakeSleep()
    event = run_hook(ToolRetry(sleep=sleep), after_tool_call(result))

    assert event.retry is False
    assert sleep.delays == []


def test_cancelled_tool_calls_are_not_retried():
    event = run_hook(
        ToolRetry(sleep=FakeSleep()),
        after_tool_call(GATEWAY_TARGET_FAILURE, cancel_message="Loop guard: stop"),
    )

    assert event.retry is False


def test_backoff_doubles_up_to_the_cap(monkeypatch):
    monkeypatch.setattr(tool_retry.random, "uniform", lambda low, high: high)
    hook = ToolRetry(base_delay_seconds=0.5, max_delay_seconds=4.0)

    assert [hook.backoff_delay(attempt) for attempt in range(1, 6)] == [0.5, 1.0, 2.0, 4.0, 4.0]
