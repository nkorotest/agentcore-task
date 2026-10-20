# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.40.0"]
# ///
"""Check the deployed IAM roles with the IAM policy simulator.

uv run scripts/check_least_privilege.py
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_OUTPUTS = REPO_ROOT / "backend" / "cdk-outputs.json"
DEPLOYED_STATE = REPO_ROOT / "SupportAgent" / "agentcore" / ".cli" / "deployed-state.json"
AGENT_MODEL = "us.amazon.nova-2-lite-v1:0"
OTHER_MODEL = "us.anthropic.claude-haiku-5-5"
TOOL_FUNCTIONS = ("support-get-order-status", "support-get-customer", "support-refund-customer")


@dataclass(frozen=True)
class Expectation:
    principal: str
    action: str
    resource: str
    allowed: bool


def discover() -> dict[str, str]:
    session = boto3.Session()
    lambda_client = session.client("lambda")
    arns = {
        name: lambda_client.get_function_configuration(FunctionName=name) for name in TOOL_FUNCTIONS
    }
    table_name = json.loads(BACKEND_OUTPUTS.read_text())["SupportAgentBackend"]["RefundsTableName"]
    resources = json.loads(DEPLOYED_STATE.read_text())["targets"]["default"]["resources"]
    gateway = resources["mcp"]["gateways"]["SupportGateway"]
    account, region = gateway["gatewayArn"].split(":")[4], gateway["gatewayArn"].split(":")[3]
    table_arn = session.client("dynamodb").describe_table(TableName=table_name)["Table"]["TableArn"]
    return {
        "gateway_role": session.client("bedrock-agentcore-control").get_gateway(
            gatewayIdentifier=gateway["gatewayId"]
        )["roleArn"],
        "runtime_role": resources["runtimes"]["support_agent"]["roleArn"],
        "gateway": gateway["gatewayArn"],
        "other_gateway": gateway["gatewayArn"].rsplit("/", 1)[0] + "/some-other-gateway",
        "agent_model": f"arn:aws:bedrock:{region}:{account}:inference-profile/{AGENT_MODEL}",
        "agent_foundation_model": f"arn:aws:bedrock:{region}::foundation-model/"
        + AGENT_MODEL.split(".", 1)[1],
        "other_model": f"arn:aws:bedrock:{region}:{account}:inference-profile/{OTHER_MODEL}",
        "orders_role": arns["support-get-order-status"]["Role"],
        "customers_role": arns["support-get-customer"]["Role"],
        "refund_role": arns["support-refund-customer"]["Role"],
        "orders_fn": arns["support-get-order-status"]["FunctionArn"],
        "customers_fn": arns["support-get-customer"]["FunctionArn"],
        "refund_fn": arns["support-refund-customer"]["FunctionArn"],
        "other_fn": arns["support-refund-customer"]["FunctionArn"].rsplit(":", 1)[0]
        + ":some-other-function",
        "refunds_table": table_arn,
        "other_table": table_arn.rsplit("/", 1)[0] + "/some-other-table",
    }


def expectations(arn: dict[str, str]) -> list[Expectation]:
    rules = [
        # The agent runtime may call its one model and its one gateway, and nothing behind it.
        Expectation("runtime_role", "bedrock:InvokeModel", "agent_model", True),
        Expectation("runtime_role", "bedrock:InvokeModel", "agent_foundation_model", True),
        Expectation("runtime_role", "bedrock:InvokeModel", "other_model", False),
        Expectation("runtime_role", "bedrock-agentcore:InvokeGateway", "gateway", True),
        Expectation("runtime_role", "bedrock-agentcore:InvokeGateway", "other_gateway", False),
        Expectation("runtime_role", "lambda:InvokeFunction", "refund_fn", False),
        Expectation("runtime_role", "dynamodb:PutItem", "refunds_table", False),
        # The gateway may invoke exactly the three tool functions.
        *(
            Expectation("gateway_role", "lambda:InvokeFunction", fn, True)
            for fn in ("orders_fn", "customers_fn", "refund_fn")
        ),
        Expectation("gateway_role", "lambda:InvokeFunction", "other_fn", False),
        Expectation("gateway_role", "dynamodb:PutItem", "refunds_table", False),
        # Read-only tools have no data-store or invoke permissions at all.
        *(
            Expectation(role, action, resource, False)
            for role in ("orders_role", "customers_role")
            for action, resource in (
                ("dynamodb:GetItem", "refunds_table"),
                ("dynamodb:PutItem", "refunds_table"),
                ("lambda:InvokeFunction", "refund_fn"),
            )
        ),
        # The refund function may only read and conditionally write its own table.
        Expectation("refund_role", "dynamodb:PutItem", "refunds_table", True),
        Expectation("refund_role", "dynamodb:GetItem", "refunds_table", True),
        *(
            Expectation("refund_role", action, "refunds_table", False)
            for action in ("dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Scan")
        ),
        Expectation("refund_role", "dynamodb:PutItem", "other_table", False),
        Expectation("refund_role", "lambda:InvokeFunction", "refund_fn", False),
    ]
    return [Expectation(arn[r.principal], r.action, arn[r.resource], r.allowed) for r in rules]


def main() -> int:
    iam = boto3.client("iam")
    failures = 0
    for rule in expectations(discover()):
        decision = iam.simulate_principal_policy(
            PolicySourceArn=rule.principal, ActionNames=[rule.action], ResourceArns=[rule.resource]
        )["EvaluationResults"][0]["EvalDecision"]
        ok = (decision == "allowed") == rule.allowed
        failures += not ok
        print(
            f"{'PASS' if ok else 'FAIL'}  {rule.principal.rsplit('/', 1)[-1]:<62} "
            f"{rule.action:<23} {rule.resource.split(':', 5)[-1]:<55} {decision}"
        )
    print(f"\n{failures} unexpected decision(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
