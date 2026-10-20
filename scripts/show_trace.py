# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.40.0"]
# ///
"""Print everything recorded for one trace: its spans and the gateway's log entries, in time order.

Spans come from CloudWatch Transaction Search (the aws/spans log group); gateway entries come from
the gateway's application log group. Both carry the same trace ID, so a single ID ties a tool call
at the gateway to the Lambda invocation behind it.

    uv run scripts/show_trace.py 6ad76c942657341540dd7ea31c7b2c9b --hours 24
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import boto3

DEPLOYED_STATE = (
    Path(__file__).resolve().parent.parent / "SupportAgent/agentcore/.cli/deployed-state.json"
)
SPANS_LOG_GROUP = "aws/spans"


def gateway_log_group() -> str:
    state = json.loads(DEPLOYED_STATE.read_text(encoding="utf-8"))
    gateway = state["targets"]["default"]["resources"]["mcp"]["gateways"]["SupportGateway"]
    return f"/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway['gatewayId']}"


def run_query(logs: Any, log_group: str, query: str, hours: float) -> list[dict[str, str]]:
    now = int(time.time())
    query_id = logs.start_query(
        logGroupName=log_group,
        startTime=now - int(hours * 3600),
        endTime=now,
        queryString=query,
    )["queryId"]
    while (response := logs.get_query_results(queryId=query_id))["status"] in (
        "Scheduled",
        "Running",
    ):
        time.sleep(1)
    return [{field["field"]: field["value"] for field in row} for row in response["results"]]


def span_lines(logs: Any, trace_id: str, hours: float) -> list[tuple[str, str]]:
    rows = run_query(
        logs,
        SPANS_LOG_GROUP,
        "fields @timestamp, name, spanId, parentSpanId, status.code as status, durationNano,"
        " resource.attributes.service.name as service"
        f" | filter traceId = '{trace_id}' | sort @timestamp asc | limit 200",
        hours,
    )
    return [
        (
            row["@timestamp"],
            f"SPAN    {row.get('name', '')}  status={row.get('status', '-')}"
            f"  duration={int(row.get('durationNano', '0')) / 1e6:.0f}ms"
            f"  span={row.get('spanId', '')} parent={row.get('parentSpanId', '-')}",
        )
        for row in rows
    ]


def gateway_lines(logs: Any, trace_id: str, hours: float) -> list[tuple[str, str]]:
    rows = run_query(
        logs,
        gateway_log_group(),
        f"fields @timestamp, @message | filter trace_id = '{trace_id}'"
        " | sort @timestamp asc | limit 200",
        hours,
    )
    lines = []
    for row in rows:
        body = json.loads(row["@message"]).get("body", {})
        details = {key: value for key, value in body.items() if key not in ("id", "isError")}
        flag = "ERROR" if body.get("isError") else "     "
        lines.append((row["@timestamp"], f"GATEWAY {flag} {json.dumps(details)}"))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_id", help="Trace ID, e.g. from a gateway log entry or a span.")
    parser.add_argument("--hours", type=float, default=24, help="How far back to search.")
    args = parser.parse_args()

    logs = boto3.client("logs")
    timeline = sorted(
        span_lines(logs, args.trace_id, args.hours) + gateway_lines(logs, args.trace_id, args.hours)
    )
    if not timeline:
        print(f"Nothing recorded for trace {args.trace_id} in the last {args.hours} hours.")
        return 1
    print(f"Trace {args.trace_id}")
    for timestamp, line in timeline:
        print(f"{timestamp}  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
