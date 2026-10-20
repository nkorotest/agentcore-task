"""Fault fixtures for the failure scenarios, active only when FAULT_INJECTION_ENABLED=true."""

# get_order_status sleeps past the Lambda timeout -> "tool timeout".
SLOW_ORDER_ID = "9001"

# get_order_status never returns a final status and tells the caller to ask again -> "LLM loop".
NEVER_SETTLING_ORDER_ID = "9002"

# get_customer fails the way an upstream CRM returning HTTP 500 would -> "HTTP 500".
FAILING_CUSTOMER_ID = "C-5000"
