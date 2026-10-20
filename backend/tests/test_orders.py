import pytest

from support_backend import faults, orders

from .lambda_context import gateway_context

CONTEXT = gateway_context("OrdersTarget___get_order_status")


def test_delayed_order_includes_delay_reason():
    result = orders.handler({"order_id": "123"}, CONTEXT)

    assert result["status"] == "DELAYED"
    assert result["customer_id"] == "C-1001"
    assert "Leipzig" in result["delay_reason"]


@pytest.mark.parametrize("order_id", ["#123", "abc", "", "   ", 123, None, "12345678901"])
def test_malformed_order_id_is_invalid_parameter(order_id):
    result = orders.handler({"order_id": order_id}, CONTEXT)

    assert result["error"]["code"] == "INVALID_PARAMETER"
    assert result["error"]["retryable"] is False


def test_unknown_order_is_not_found():
    result = orders.handler({"order_id": "404"}, CONTEXT)

    assert result["error"]["code"] == "NOT_FOUND"


def test_slow_order_sleeps_when_fault_injection_enabled(fault_injection, monkeypatch):
    sleeps = []
    monkeypatch.setattr(orders.time, "sleep", sleeps.append)

    orders.handler({"order_id": faults.SLOW_ORDER_ID}, CONTEXT)

    assert sleeps == [30.0]


def test_never_settling_order_asks_caller_to_check_again(fault_injection):
    result = orders.handler({"order_id": faults.NEVER_SETTLING_ORDER_ID}, CONTEXT)

    assert result["status"] == "STATUS_UPDATING"


@pytest.mark.parametrize("order_id", [faults.SLOW_ORDER_ID, faults.NEVER_SETTLING_ORDER_ID])
def test_fault_ids_are_unknown_when_fault_injection_disabled(order_id, monkeypatch):
    monkeypatch.setattr(orders.time, "sleep", pytest.fail)

    result = orders.handler({"order_id": order_id}, CONTEXT)

    assert result["error"]["code"] == "NOT_FOUND"
