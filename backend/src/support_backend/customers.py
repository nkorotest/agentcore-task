"""get_customer tool: a customer's profile and order IDs."""

import copy
import re
from typing import Any

from . import faults
from .config import load_settings
from .errors import NotFoundError, UpstreamServiceError
from .observability import tool_handler
from .seed_data import CUSTOMERS
from .validation import require_string

CUSTOMER_ID_PATTERN = re.compile(r"C-\d{4}")


@tool_handler("get_customer")
def handler(arguments: dict[str, Any]) -> dict[str, Any]:
    customer_id = require_string(
        arguments, "customer_id", max_length=6, pattern=CUSTOMER_ID_PATTERN
    )

    if load_settings().fault_injection_enabled and customer_id == faults.FAILING_CUSTOMER_ID:
        raise UpstreamServiceError("CRM service responded with HTTP 500 Internal Server Error.")

    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} does not exist.")
    return copy.deepcopy(customer)
