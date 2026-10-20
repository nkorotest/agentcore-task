import os

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

GATEWAY_URL_ENV_VAR = "AGENTCORE_GATEWAY_SUPPORTGATEWAY_URL"


def get_support_gateway_mcp_client() -> MCPClient:
    """MCP client for SupportGateway; requests are SigV4-signed with the runtime's IAM role."""
    url = os.environ.get(GATEWAY_URL_ENV_VAR)
    if not url:
        raise RuntimeError(
            f"{GATEWAY_URL_ENV_VAR} is not set. Deploy the gateway with `agentcore deploy` first."
        )
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            url, aws_service="bedrock-agentcore", aws_region=region
        )
    )
