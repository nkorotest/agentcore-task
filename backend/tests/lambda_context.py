from types import SimpleNamespace


def gateway_context(tool_name: str) -> SimpleNamespace:
    """A Lambda context shaped like the one AgentCore Gateway sends to Lambda targets."""
    return SimpleNamespace(
        client_context=SimpleNamespace(
            custom={
                "bedrockAgentCoreToolName": tool_name,
                "bedrockAgentCoreGatewayId": "gw-test",
                "bedrockAgentCoreTargetId": "target-test",
                "bedrockAgentCoreMcpMessageId": "1",
                "bedrockAgentCoreAwsRequestId": "req-test",
            }
        )
    )
