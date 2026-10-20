"""get_order_status tool: an order's status, shipping details and delay reason."""

import copy
import re
import time
from typing import Any

from . import faults
from .config import load_settings
from .errors import NotFoundError
from .observability import tool_handler
from .seed_data import ORDERS
from .validation import require_string

ORDER_ID_PATTERN = re.compile(r"\d{1,10}")


@tool_handler("get_order_status")
def handler(arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = require_string(arguments, "order_id", max_length=10, pattern=ORDER_ID_PATTERN)

    settings = load_settings()
    if settings.fault_injection_enabled:
        if order_id == faults.SLOW_ORDER_ID:
            time.sleep(settings.slow_tool_delay_seconds)
        elif order_id == faults.NEVER_SETTLING_ORDER_ID:
            return {
                "order_id": order_id,
                "status": "STATUS_UPDATING",
                "message": (
                    "The order status is being recalculated. "
                    "Call get_order_status again to get the final status."
                ),
            }

    order = ORDERS.get(order_id)
    if order is None:
        raise NotFoundError(f"Order {order_id} does not exist.")
    return copy.deepcopy(order)
