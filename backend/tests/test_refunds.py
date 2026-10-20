import pytest

from support_backend import refunds

from .lambda_context import gateway_context

CONTEXT = gateway_context("RefundsTarget___refund_customer")


def refund_request(**overrides):
    request = {
        "order_id": "123",
        "amount_cents": 2500,
        "reason": "Delivery is a week late",
        "idempotency_key": "operation-123",
    }
    return {**request, **overrides}


def test_creates_refund(refunds_table):
    result = refunds.handler(refund_request(), CONTEXT)

    assert result["refund_id"].startswith("rf_")
    assert result["amount_cents"] == 2500
    assert result["status"] == "COMPLETED"
    assert result["replayed"] is False


def test_retry_with_same_idempotency_key_returns_existing_refund(refunds_table):
    first = refunds.handler(refund_request(), CONTEXT)
    retry = refunds.handler(refund_request(), CONTEXT)

    assert retry["refund_id"] == first["refund_id"]
    assert retry["replayed"] is True
    assert refunds_table.scan()["Count"] == 1


def test_same_key_with_different_amount_is_a_conflict(refunds_table):
    first = refunds.handler(refund_request(), CONTEXT)
    result = refunds.handler(refund_request(amount_cents=9900), CONTEXT)

    assert result["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert result["error"]["details"]["existing_refund_id"] == first["refund_id"]
    assert refunds_table.scan()["Count"] == 1


def test_different_keys_create_separate_refunds(refunds_table):
    refunds.handler(refund_request(idempotency_key="operation-1"), CONTEXT)
    refunds.handler(refund_request(idempotency_key="operation-2"), CONTEXT)

    assert refunds_table.scan()["Count"] == 2


def test_refund_is_recorded_for_the_customer_who_placed_the_order(refunds_table):
    refunds.handler(refund_request(order_id="777"), CONTEXT)

    item = refunds_table.get_item(Key={"idempotency_key": "operation-123"})["Item"]
    assert item["customer_id"] == "C-1002"


def test_refund_above_order_total_is_rejected(refunds_table):
    result = refunds.handler(refund_request(amount_cents=12901), CONTEXT)

    assert result["error"]["code"] == "REFUND_EXCEEDS_ORDER_TOTAL"
    assert refunds_table.scan()["Count"] == 0


def test_unknown_order_is_not_found(refunds_table):
    result = refunds.handler(refund_request(order_id="404"), CONTEXT)

    assert result["error"]["code"] == "NOT_FOUND"


def test_whole_number_float_amount_is_accepted(refunds_table):
    result = refunds.handler(refund_request(amount_cents=2500.0), CONTEXT)

    assert result["amount_cents"] == 2500


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount_cents": 0},
        {"amount_cents": -500},
        {"amount_cents": 25.5},
        {"amount_cents": "2500"},
        {"amount_cents": True},
        {"reason": ""},
        {"reason": "x" * 501},
        {"idempotency_key": "has spaces"},
        {"idempotency_key": "k" * 129},
        {"order_id": None},
    ],
)
def test_invalid_parameters_are_rejected_before_writing(refunds_table, overrides):
    result = refunds.handler(refund_request(**overrides), CONTEXT)

    assert result["error"]["code"] == "INVALID_PARAMETER"
    assert refunds_table.scan()["Count"] == 0
