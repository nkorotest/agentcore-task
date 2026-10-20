"""Shared MCP access to SupportGateway for the scripts in this folder.

Requests are SigV4-signed with your local AWS credentials (AWS_PROFILE), exactly like the agent's
own requests, so Gateway policies apply to them in the same way.
"""

import json
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mcp import ClientSession
from mcp.shared.exceptions import McpError
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

GATEWAY_NAME = "SupportGateway"
DEPLOYED_STATE = (
    Path(__file__).resolve().parent.parent / "SupportAgent/agentcore/.cli/deployed-state.json"
)
REGION_IN_URL = re.compile(r"\.bedrock-agentcore\.([a-z0-9-]+)\.amazonaws\.com")


@dataclass(frozen=True)
class ToolOutcome:
    """How a tool call ended.

    result:     the tool ran and returned data (which may itself describe a business error);
    tool_error: the tool failed while running (isError=true, e.g. a Lambda timeout or crash);
    rejected:   the gateway refused the call before running the tool (e.g. a policy DENY).
    """

    kind: Literal["result", "tool_error", "rejected"]
    text: str

    @property
    def data(self) -> Any:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            return None


def resolve_gateway_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    if DEPLOYED_STATE.exists():
        state = json.loads(DEPLOYED_STATE.read_text(encoding="utf-8"))
        gateways = state["targets"]["default"]["resources"].get("mcp", {}).get("gateways", {})
        if url := gateways.get(GATEWAY_NAME, {}).get("gatewayUrl"):
            return url
    sys.exit(f"{GATEWAY_NAME} URL not found in {DEPLOYED_STATE}. Deploy it or pass --url.")


def _region(url: str) -> str | None:
    if match := REGION_IN_URL.search(url):
        return match.group(1)
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")


@asynccontextmanager
async def gateway_session(url: str) -> AsyncIterator[ClientSession]:
    client = aws_iam_streamablehttp_client(
        url, aws_service="bedrock-agentcore", aws_region=_region(url)
    )
    async with (
        client as (read_stream, write_stream, _),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        yield session


async def call_tool(session: ClientSession, tool: str, arguments: dict[str, Any]) -> ToolOutcome:
    try:
        result = await session.call_tool(tool, arguments)
    except McpError as error:
        return ToolOutcome("rejected", error.error.message)
    text = "\n".join(getattr(item, "text", item.model_dump_json()) for item in result.content)
    return ToolOutcome("tool_error" if result.isError else "result", text)
