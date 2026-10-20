import os

import aws_cdk as cdk

from infra.backend_stack import SupportBackendStack

app = cdk.App()

# Fault fixtures (see src/support_backend/faults.py) exist only for the observability demo.
fault_injection_enabled = str(app.node.try_get_context("faultInjection")).lower() == "true"

SupportBackendStack(
    app,
    "SupportAgentBackend",
    fault_injection_enabled=fault_injection_enabled,
    description="Business tools (Lambda + DynamoDB) behind the support agent's AgentCore Gateway.",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    ),
)
cdk.Tags.of(app).add("project", "support-agent")

app.synth()
