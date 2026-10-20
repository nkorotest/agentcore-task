import os

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

# Set by AgentCore for the deployed runtime and by `agentcore dev` locally.
GATEWAY_URL_ENV_VAR = "AGENTCORE_GATEWAY_SUPPORTGATEWAY_URL"


def get_support_gateway_mcp_client() -> MCPClient:
    """MCP client for SupportGateway, which exposes the order, customer and refund tools.

    Requests are SigV4-signed with the runtime's IAM role (the gateway uses AWS_IAM inbound auth),
    so no credentials are stored in code or configuration.
    """
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
