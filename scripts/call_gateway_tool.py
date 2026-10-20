# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=1.28.1,<2", "mcp-proxy-for-aws>=1.1.0"]
# ///
r"""Call SupportGateway tools directly over MCP, bypassing the agent and the LLM.

Requests are SigV4-signed with your local AWS credentials (AWS_PROFILE), exactly like the agent's
own requests, so Gateway policies apply to them in the same way.

    uv run scripts/call_gateway_tool.py list
    uv run scripts/call_gateway_tool.py call OrdersTarget___get_order_status "{\"order_id\": \"123\"}"

The gateway URL is read from the AgentCore deployed state; pass --url to override it.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

GATEWAY_NAME = "SupportGateway"
DEPLOYED_STATE = (
    Path(__file__).resolve().parent.parent
    / "SupportAgent"
    / "agentcore"
    / ".cli"
    / "deployed-state.json"
)
REGION_IN_URL = re.compile(r"\.bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com")


def _find_gateway_url(node: Any) -> str | None:
    if isinstance(node, dict):
        gateway = node.get(GATEWAY_NAME)
        if isinstance(gateway, dict) and isinstance(gateway.get("gatewayUrl"), str):
            return gateway["gatewayUrl"]
        children = node.values()
    elif isinstance(node, list):
        children = node
    else:
        return None
    return next((url for child in children if (url := _find_gateway_url(child))), None)


def resolve_gateway_url(explicit_url: str | None) -> str:
    if explicit_url:
        return explicit_url
    if DEPLOYED_STATE.exists():
        url = _find_gateway_url(json.loads(DEPLOYED_STATE.read_text(encoding="utf-8")))
        if url:
            return url
    sys.exit(f"{GATEWAY_NAME} URL not found in {DEPLOYED_STATE}. Deploy it or pass --url.")


def resolve_region(url: str) -> str | None:
    if match := REGION_IN_URL.search(url):
        return match.group(1)
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


def print_result(result: Any) -> None:
    for item in result.content:
        text = getattr(item, "text", None)
        if text is None:
            print(item.model_dump_json(indent=2))
            continue
        try:
            print(json.dumps(json.loads(text), indent=2))
        except json.JSONDecodeError:
            print(text)


async def run(args: argparse.Namespace) -> int:
    url = resolve_gateway_url(args.url)
    client = aws_iam_streamablehttp_client(
        url, aws_service="bedrock-agentcore", aws_region=resolve_region(url)
    )
    async with (
        client as (read_stream, write_stream, _),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        if args.command == "list":
            for tool in (await session.list_tools()).tools:
                print(tool.name)
            return 0

        result = await session.call_tool(args.tool, json.loads(args.arguments))
        print_result(result)
        if result.isError:
            print("Tool call failed (isError=true).", file=sys.stderr)
            return 1
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", help="Gateway MCP URL (defaults to the deployed SupportGateway).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List the tools the gateway exposes.")
    call = commands.add_parser("call", help="Call one tool.")
    call.add_argument("tool", help="Full tool name, e.g. RefundsTarget___refund_customer.")
    call.add_argument("arguments", nargs="?", default="{}", help="Tool arguments as a JSON object.")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
