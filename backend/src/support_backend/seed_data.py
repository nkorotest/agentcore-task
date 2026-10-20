"""Synthetic orders and customers standing in for the order-management and CRM systems.

All names and emails are fictional. Order 777 is deliberately large ($7,500) so that a $5,000 refund
passes the backend's own checks and can only be stopped by the Gateway policy.
"""

from typing import Any

ORDERS: dict[str, dict[str, Any]] = {
    "123": {
        "order_id": "123",
        "customer_id": "C-1001",
        "status": "DELAYED",
        "placed_at": "2026-10-12",
        "items": [{"sku": "KB-200", "name": "Mechanical keyboard", "quantity": 1}],
        "total_cents": 12900,
        "currency": "USD",
        "carrier": "DHL Express",
        "tracking_number": "JD014600006281",
        "original_estimated_delivery": "2026-10-16",
        "estimated_delivery": "2026-10-23",
        "delay_reason": (
            "Severe weather closed the carrier's Leipzig hub. The parcel is held there and will "
            "resume transit on 2026-10-21."
        ),
    },
    "456": {
        "order_id": "456",
        "customer_id": "C-1002",
        "status": "DELIVERED",
        "placed_at": "2026-09-28",
        "items": [{"sku": "HP-750", "name": "Noise-cancelling headphones", "quantity": 1}],
        "total_cents": 24900,
        "currency": "USD",
        "carrier": "UPS",
        "tracking_number": "1Z999AA10123456784",
        "delivered_at": "2026-10-02",
    },
    "777": {
        "order_id": "777",
        "customer_id": "C-1002",
        "status": "SHIPPED",
        "placed_at": "2026-10-15",
        "items": [{"sku": "WS-9000", "name": "Workstation laptop", "quantity": 1}],
        "total_cents": 750000,
        "currency": "USD",
        "carrier": "FedEx",
        "tracking_number": "794644790138",
        "estimated_delivery": "2026-10-22",
    },
    "789": {
        "order_id": "789",
        "customer_id": "C-1001",
        "status": "PROCESSING",
        "placed_at": "2026-10-19",
        "items": [{"sku": "MS-310", "name": "Wireless mouse", "quantity": 2}],
        "total_cents": 7800,
        "currency": "USD",
    },
}

CUSTOMERS: dict[str, dict[str, Any]] = {
    "C-1001": {
        "customer_id": "C-1001",
        "name": "Alice Martin",
        "email": "alice.martin@example.com",
        "loyalty_tier": "GOLD",
        "member_since": "2021-03-14",
        "order_ids": ["123", "789"],
    },
    "C-1002": {
        "customer_id": "C-1002",
        "name": "Bob Novak",
        "email": "bob.novak@example.com",
        "loyalty_tier": "STANDARD",
        "member_since": "2024-07-02",
        "order_ids": ["456", "777"],
    },
}
