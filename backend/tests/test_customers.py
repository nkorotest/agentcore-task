import pytest

from support_backend import customers, faults
from support_backend.errors import UpstreamServiceError

from .lambda_context import gateway_context

CONTEXT = gateway_context("CustomersTarget___get_customer")


def test_returns_customer_profile():
    result = customers.handler({"customer_id": "C-1001"}, CONTEXT)

    assert result["name"] == "Alice Martin"
    assert result["order_ids"] == ["123", "789"]


@pytest.mark.parametrize("customer_id", ["123", "c-1001", "C-10011", "", None])
def test_malformed_customer_id_is_invalid_parameter(customer_id):
    result = customers.handler({"customer_id": customer_id}, CONTEXT)

    assert result["error"]["code"] == "INVALID_PARAMETER"


def test_unknown_customer_is_not_found():
    result = customers.handler({"customer_id": "C-9999"}, CONTEXT)

    assert result["error"]["code"] == "NOT_FOUND"


def test_upstream_failure_fails_the_invocation(fault_injection):
    with pytest.raises(UpstreamServiceError):
        customers.handler({"customer_id": faults.FAILING_CUSTOMER_ID}, CONTEXT)
