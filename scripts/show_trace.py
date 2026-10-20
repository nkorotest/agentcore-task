# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.40.0"]
# ///
"""Print everything recorded for one trace, in time order: agent, gateway and Lambda.

- Agent spans: written by AgentCore Runtime to the "spans" stream of the runtime's log group.
- Gateway and Lambda spans: CloudWatch Transaction Search (the aws/spans log group).
- Gateway log entries (requests, policy decisions, errors): the gateway's application log group.

All of them carry the same trace ID, so one ID follows a request from the agent's model call through
the gateway's policy decision to the Lambda invocation.

    uv run scripts/show_trace.py <trace-id>
    uv run scripts/show_trace.py --session <runtime-session-id>   # every trace of an agent session
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
TRANSACTION_SEARCH_LOG_GROUP = "aws/spans"
RUNTIME_LOG_GROUP_PREFIX = "/aws/bedrock-agentcore/runtimes/"
SPAN_FIELDS = "fields @timestamp, name, spanId, parentSpanId, status.code as status, durationNano"


def gateway_log_group() -> str:
    state = json.loads(DEPLOYED_STATE.read_text(encoding="utf-8"))
    gateway = state["targets"]["default"]["resources"]["mcp"]["gateways"]["SupportGateway"]
    return f"/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway['gatewayId']}"


def runtime_log_groups(logs: Any) -> list[str]:
    groups = logs.describe_log_groups(logGroupNamePrefix=RUNTIME_LOG_GROUP_PREFIX)["logGroups"]
    return [group["logGroupName"] for group in groups]


def runtime_spans(logs: Any, needle: str, hours: float) -> list[dict[str, Any]]:
    """Agent spans from the runtime's "spans" log stream whose JSON contains the given text."""
    spans = []
    start = int((time.time() - hours * 3600) * 1000)
    for group in runtime_log_groups(logs):
        paginator = logs.get_paginator("filter_log_events")
        pages = paginator.paginate(
            logGroupName=group,
            logStreamNames=["spans"],
            startTime=start,
            filterPattern=f'"{needle}"',
        )
        spans += [json.loads(event["message"]) for page in pages for event in page["events"]]
    return spans


def agent_span_lines(logs: Any, trace_id: str, hours: float) -> list[tuple[str, str]]:
    lines = []
    for span in runtime_spans(logs, trace_id, hours):
        if span.get("traceId") != trace_id:
            continue
        started = (
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(span["startTimeUnixNano"] / 1e9))
            + f".{int(span['startTimeUnixNano'] / 1e6) % 1000:03d}"
        )
        status = span.get("status", {}).get("code", "UNSET")
        lines.append(
            (
                started,
                f"AGENT   {span['name']}  status={status}"
                f"  duration={span['durationNano'] / 1e6:.0f}ms"
                f"  span={span['spanId']} parent={span.get('parentSpanId', '-')}",
            )
        )
    return lines


def run_query(logs: Any, log_groups: list[str], query: str, hours: float) -> list[dict[str, str]]:
    if not log_groups:
        return []
    now = int(time.time())
    query_id = logs.start_query(
        logGroupNames=log_groups,
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


def span_lines(logs: Any, source: str, groups: list[str], trace_id: str, hours: float) -> list:
    rows = run_query(
        logs,
        groups,
        f"{SPAN_FIELDS} | filter traceId = '{trace_id}' | sort @timestamp asc | limit 500",
        hours,
    )
    return [
        (
            row["@timestamp"],
            f"{source:<7} {row.get('name', '')}  status={row.get('status', '-')}"
            f"  duration={int(row.get('durationNano', '0')) / 1e6:.0f}ms"
            f"  span={row.get('spanId', '')} parent={row.get('parentSpanId', '-')}",
        )
        for row in rows
    ]


def gateway_lines(logs: Any, trace_id: str, hours: float) -> list[tuple[str, str]]:
    rows = run_query(
        logs,
        [gateway_log_group()],
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


def traces_for_session(logs: Any, session_id: str, hours: float) -> list[str]:
    spans = runtime_spans(logs, session_id, hours)
    first_seen = {}
    for span in sorted(spans, key=lambda span: span["startTimeUnixNano"]):
        if span.get("attributes", {}).get("session.id") == session_id:
            first_seen.setdefault(span["traceId"], span["startTimeUnixNano"])
    return list(first_seen)


def print_trace(logs: Any, trace_id: str, hours: float) -> bool:
    timeline = sorted(
        agent_span_lines(logs, trace_id, hours)
        + span_lines(logs, "SPAN", [TRANSACTION_SEARCH_LOG_GROUP], trace_id, hours)
        + gateway_lines(logs, trace_id, hours)
    )
    if not timeline:
        print(f"Nothing recorded for trace {trace_id} in the last {hours} hours.")
        return False
    print(f"Trace {trace_id}")
    for timestamp, line in timeline:
        print(f"{timestamp}  {line}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("trace_id", nargs="?", help="Trace ID from a span or gateway log entry.")
    parser.add_argument("--session", help="Show every trace of this runtime session instead.")
    parser.add_argument("--hours", type=float, default=24, help="How far back to search.")
    args = parser.parse_args()
    if not args.trace_id and not args.session:
        parser.error("give a trace ID or --session")

    logs = boto3.client("logs")
    trace_ids = traces_for_session(logs, args.session, args.hours) if args.session else []
    if args.session:
        print(f"Session {args.session}: {len(trace_ids)} trace(s)\n")
    found = [print_trace(logs, trace_id, args.hours) for trace_id in trace_ids or [args.trace_id]]
    return 0 if all(found) and found else 1


if __name__ == "__main__":
    sys.exit(main())
