from itertools import count

from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent, HookRegistry

from reliability import LoopGuard

_tool_use_ids = count()


def tool_call(order_id="9002", tool_use_id=None):
    return BeforeToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={
            "toolUseId": tool_use_id or f"tool-{next(_tool_use_ids)}",
            "name": "OrdersTarget___get_order_status",
            "input": {"order_id": order_id},
        },
        invocation_state={},
    )


def make_registry(guard):
    registry = HookRegistry()
    guard.register_hooks(registry)
    return registry


def run(registry, event):
    event, _ = registry.invoke_callbacks(event)
    return event


def test_identical_calls_beyond_the_limit_are_cancelled():
    registry = make_registry(LoopGuard(max_identical_calls=3))

    cancellations = [run(registry, tool_call()).cancel_tool for _ in range(4)]

    assert cancellations[:3] == [False, False, False]
    assert "already called 3 times with the same input" in cancellations[3]


def test_retries_of_the_same_tool_use_are_not_counted():
    registry = make_registry(LoopGuard(max_identical_calls=1))

    first = run(registry, tool_call(tool_use_id="retried"))
    retry = run(registry, tool_call(tool_use_id="retried"))

    assert first.cancel_tool is False
    assert retry.cancel_tool is False


def test_total_tool_calls_per_request_are_capped():
    registry = make_registry(LoopGuard(max_tool_calls=10))

    cancellations = [run(registry, tool_call(order_id=str(n))).cancel_tool for n in range(11)]

    assert cancellations[:10] == [False] * 10
    assert "already made 10 tool calls" in cancellations[10]


def test_limits_reset_for_each_request():
    registry = make_registry(LoopGuard(max_identical_calls=1))

    run(registry, tool_call())
    run(registry, BeforeInvocationEvent(agent=None))

    assert run(registry, tool_call()).cancel_tool is False
