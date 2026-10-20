# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=1.28.1,<2", "mcp-proxy-for-aws>=1.1.0"]
# ///
"""Call SupportGateway tools directly over MCP (no agent, no model).

    uv run scripts/call_gateway_tool.py list
    uv run scripts/call_gateway_tool.py call OrdersTarget___get_order_status '{"order_id": "123"}'

Exit codes: 0 result, 1 tool error, 2 rejected by the gateway (e.g. policy DENY).
"""

import argparse
import asyncio
import json
import sys

from gateway_client import call_tool, gateway_session, resolve_gateway_url

EXIT_CODES = {"result": 0, "tool_error": 1, "rejected": 2}


async def run(args: argparse.Namespace) -> int:
    async with gateway_session(resolve_gateway_url(args.url)) as session:
        if args.command == "list":
            for tool in (await session.list_tools()).tools:
                print(tool.name)
            return 0

        outcome = await call_tool(session, args.tool, json.loads(args.arguments))
        if outcome.kind == "rejected":
            print(f"Gateway rejected the call: {outcome.text}", file=sys.stderr)
        elif outcome.kind == "tool_error":
            print(f"Tool call failed (isError=true): {outcome.text}", file=sys.stderr)
        else:
            data = outcome.data
            print(json.dumps(data, indent=2) if data is not None else outcome.text)
        return EXIT_CODES[outcome.kind]


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
