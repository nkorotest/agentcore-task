import json
import os
from pathlib import Path

import aws_cdk as cdk

from infra.backend_stack import SupportBackendStack
from infra.observability_stack import SupportObservabilityStack

# The gateway is deployed by the AgentCore CLI; its identifiers are read from the CLI's state.
AGENTCORE_STATE = (
    Path(__file__).resolve().parent.parent / "SupportAgent/agentcore/.cli/deployed-state.json"
)


def deployed_gateway() -> dict[str, str] | None:
    if not AGENTCORE_STATE.exists():
        return None
    targets = json.loads(AGENTCORE_STATE.read_text(encoding="utf-8")).get("targets", {})
    gateways = targets.get("default", {}).get("resources", {}).get("mcp", {}).get("gateways", {})
    return gateways.get("SupportGateway")


app = cdk.App()
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

# Fault fixtures (see src/support_backend/faults.py) exist only for the observability demo.
fault_injection_enabled = str(app.node.try_get_context("faultInjection")).lower() == "true"

SupportBackendStack(
    app,
    "SupportAgentBackend",
    fault_injection_enabled=fault_injection_enabled,
    description="Business tools (Lambda + DynamoDB) behind the support agent's AgentCore Gateway.",
    env=env,
)

gateway = deployed_gateway()
if gateway:
    SupportObservabilityStack(
        app,
        "SupportAgentObservability",
        gateway_arn=gateway["gatewayArn"],
        gateway_id=gateway["gatewayId"],
        description="Gateway log and trace delivery, and saved Logs Insights queries.",
        env=env,
    )
cdk.Tags.of(app).add("project", "support-agent")

app.synth()
