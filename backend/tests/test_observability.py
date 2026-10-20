from types import SimpleNamespace

from support_backend.observability import gateway_metadata

from .lambda_context import gateway_context


def test_gateway_metadata_maps_client_context_fields():
    metadata = gateway_metadata(gateway_context("OrdersTarget___get_order_status"))

    assert metadata == {
        "gateway_tool_name": "OrdersTarget___get_order_status",
        "gateway_id": "gw-test",
        "gateway_target_id": "target-test",
        "mcp_message_id": "1",
        "gateway_request_id": "req-test",
    }


def test_gateway_metadata_tolerates_missing_client_context():
    assert gateway_metadata(SimpleNamespace(client_context=None)) == {}
    assert gateway_metadata(None) == {}
