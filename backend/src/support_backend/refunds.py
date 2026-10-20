"""refund_customer tool.

Refunds are written with a conditional put on the idempotency key, so a retried call returns
the stored refund instead of creating a second one. The $1,000 limit is enforced by the gateway
policy, not here.
"""

import hashlib
import re
import uuid
from datetime import UTC, datetime
from functools import cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import load_settings
from .errors import IdempotencyConflictError, NotFoundError, RefundExceedsOrderTotalError
from .observability import logger, tool_handler
from .orders import ORDER_ID_PATTERN
from .seed_data import ORDERS
from .validation import require_int, require_string

IDEMPOTENCY_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")
MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_REASON_LENGTH = 500

# Standard retry mode: exponential backoff with jitter for throttling and transient DynamoDB errors.
_DYNAMODB_CONFIG = Config(
    retries={"mode": "standard", "max_attempts": 5},
    connect_timeout=2,
    read_timeout=3,
)


@cache
def _refunds_table(table_name: str) -> Any:
    return boto3.resource("dynamodb", config=_DYNAMODB_CONFIG).Table(table_name)


class RefundService:
    def __init__(self, table: Any) -> None:
        self._table = table

    def refund(
        self, *, order_id: str, amount_cents: int, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        order = ORDERS.get(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} does not exist.")
        if amount_cents > order["total_cents"]:
            raise RefundExceedsOrderTotalError(
                f"Refund of {amount_cents} cents exceeds the order total of "
                f"{order['total_cents']} cents.",
                details={"order_total_cents": order["total_cents"]},
            )

        request_fingerprint = _fingerprint(order_id, amount_cents)
        record = {
            "idempotency_key": idempotency_key,
            "refund_id": f"rf_{uuid.uuid4().hex}",
            "order_id": order_id,
            "customer_id": order["customer_id"],
            "amount_cents": amount_cents,
            "currency": order["currency"],
            "reason": reason,
            "status": "COMPLETED",
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "request_fingerprint": request_fingerprint,
        }
        try:
            self._table.put_item(
                Item=record, ConditionExpression="attribute_not_exists(idempotency_key)"
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            return self._replay(idempotency_key, request_fingerprint)

        logger.info(
            "Refund created",
            extra={"refund_id": record["refund_id"], "idempotency_key": idempotency_key},
        )
        return _to_result(record, replayed=False)

    def _replay(self, idempotency_key: str, request_fingerprint: str) -> dict[str, Any]:
        existing = self._table.get_item(
            Key={"idempotency_key": idempotency_key}, ConsistentRead=True
        ).get("Item")
        if existing is None:
            # Refund records are never deleted, so a failed condition implies the item exists.
            raise RuntimeError(f"Refund for idempotency key {idempotency_key!r} vanished.")
        if existing["request_fingerprint"] != request_fingerprint:
            raise IdempotencyConflictError(
                f"Idempotency key {idempotency_key!r} was already used for a different refund.",
                details={"existing_refund_id": existing["refund_id"]},
            )
        logger.info(
            "Refund replayed for a retried operation",
            extra={"refund_id": existing["refund_id"], "idempotency_key": idempotency_key},
        )
        return _to_result(existing, replayed=True)


def _fingerprint(order_id: str, amount_cents: int) -> str:
    return hashlib.sha256(f"{order_id}:{amount_cents}".encode()).hexdigest()


def _to_result(record: dict[str, Any], *, replayed: bool) -> dict[str, Any]:
    return {
        "refund_id": record["refund_id"],
        "order_id": record["order_id"],
        "amount_cents": int(record["amount_cents"]),  # DynamoDB returns numbers as Decimal
        "currency": record["currency"],
        "status": record["status"],
        "created_at": record["created_at"],
        "idempotency_key": record["idempotency_key"],
        "replayed": replayed,
    }


@tool_handler("refund_customer")
def handler(arguments: dict[str, Any]) -> dict[str, Any]:
    order_id = require_string(arguments, "order_id", max_length=10, pattern=ORDER_ID_PATTERN)
    amount_cents = require_int(arguments, "amount_cents", minimum=1)
    reason = require_string(arguments, "reason", max_length=MAX_REASON_LENGTH)
    idempotency_key = require_string(
        arguments,
        "idempotency_key",
        max_length=MAX_IDEMPOTENCY_KEY_LENGTH,
        pattern=IDEMPOTENCY_KEY_PATTERN,
    )

    table_name = load_settings().refunds_table_name
    if not table_name:
        raise RuntimeError("REFUNDS_TABLE_NAME is not configured.")
    return RefundService(_refunds_table(table_name)).refund(
        order_id=order_id,
        amount_cents=amount_cents,
        reason=reason,
        idempotency_key=idempotency_key,
    )
