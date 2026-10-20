# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3>=1.40.0"]
# ///
"""Check whether an AWS account can host this project (AgentCore Runtime, Memory, Gateway, Bedrock).

Read-only by default:

    uv run scripts/check_account_readiness.py --profile old-account

Optional checks that create something:
  --check-claude   calls Claude Haiku 5.5 once (about 10 tokens). The first call to a third-party
                   model subscribes the account to it in AWS Marketplace (pay per use, no fee).
  --probe-memory   creates an empty AgentCore Memory, waits until it is active, then deletes it.
"""

import argparse
import sys
import time
from collections.abc import Callable

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

AGENTCORE_QUOTAS = {
    "L-F4575653": "Total Agents per Account",
    "L-9B442722": "Endpoints per Agent",
    "L-61A3A6D8": "Versions per Agent",
    "L-3E5722B2": "Active Session Workloads per Account",
    "L-81002DCC": "Memories",
    "L-F83DDFE4": "Memory strategies per account",
    "L-EAB901C0": "Memory strategies per memory",
}
REQUIRED_ACTIONS = [
    "bedrock-agentcore:CreateAgentRuntime",
    "bedrock-agentcore:CreateMemory",
    "bedrock-agentcore:CreateGateway",
    "bedrock-agentcore:CreatePolicyEngine",
    "bedrock:InvokeModel",
    "cloudformation:CreateStack",
    "iam:CreateRole",
    "lambda:CreateFunction",
    "dynamodb:CreateTable",
]
FIRST_PARTY_MODEL = "us.amazon.nova-micro-v1:0"
AGENT_MODEL = "us.anthropic.claude-haiku-5-5"
_CLIENT_CONFIG = Config(retries={"max_attempts": 2}, connect_timeout=5, read_timeout=30)

Result = tuple[str, str]  # (PASS | FAIL | WARN | SKIP, detail)


class Checks:
    def __init__(self, session: boto3.Session, region: str) -> None:
        self.session = session
        self.region = region
        self.caller_arn = ""

    def client(self, service: str):
        return self.session.client(service, region_name=self.region, config=_CLIENT_CONFIG)

    def identity(self) -> Result:
        identity = self.client("sts").get_caller_identity()
        self.caller_arn = identity["Arn"]
        return "PASS", f"account {identity['Account']} as {identity['Arn']}"

    def organization(self) -> Result:
        try:
            org = self.client("organizations").describe_organization()["Organization"]
        except ClientError as error:
            if error.response["Error"]["Code"] == "AWSOrganizationsNotInUseException":
                return "PASS", "standalone account, no service control policies"
            raise
        return "WARN", f"member of organization {org['Id']}; its SCPs may block services"

    def permissions(self) -> Result:
        arn = self.caller_arn
        if ":assumed-role/" in arn:  # simulate the role behind the session
            account, role = arn.split(":")[4], arn.split("/")[1]
            arn = f"arn:aws:iam::{account}:role/{role}"
        try:
            results = self.client("iam").simulate_principal_policy(
                PolicySourceArn=arn, ActionNames=REQUIRED_ACTIONS
            )["EvaluationResults"]
        except ClientError as error:
            return "SKIP", f"cannot simulate {arn}: {error.response['Error']['Code']}"
        denied = [r["EvalActionName"] for r in results if r["EvalDecision"] != "allowed"]
        return (
            ("FAIL", f"not allowed: {', '.join(denied)}")
            if denied
            else (
                "PASS",
                f"{len(REQUIRED_ACTIONS)} deployment actions allowed",
            )
        )

    def agentcore_quotas(self) -> Result:
        values = {}
        paginator = self.client("service-quotas").get_paginator("list_service_quotas")
        for page in paginator.paginate(ServiceCode="bedrock-agentcore"):
            for quota in page["Quotas"]:
                if quota["QuotaCode"] in AGENTCORE_QUOTAS:
                    values[AGENTCORE_QUOTAS[quota["QuotaCode"]]] = int(quota["Value"])
        zero = [name for name, value in values.items() if value == 0]
        summary = ", ".join(f"{name}={value}" for name, value in values.items())
        return ("FAIL", f"zero: {', '.join(zero)}") if zero else ("PASS", summary)

    def bedrock(self, model_id: str) -> Result:
        response = self.client("bedrock-runtime").converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with OK."}]}],
            inferenceConfig={"maxTokens": 5},
        )
        return (
            "PASS",
            f"{model_id} answered {response['output']['message']['content'][0]['text']!r}",
        )

    def memory_probe(self) -> Result:
        control = self.client("bedrock-agentcore-control")
        memory = control.create_memory(
            name=f"readiness_probe_{int(time.time())}", eventExpiryDuration=7
        )["memory"]
        try:
            control.get_waiter("memory_created").wait(
                memoryId=memory["id"], WaiterConfig={"Delay": 10, "MaxAttempts": 30}
            )
        finally:
            control.delete_memory(memoryId=memory["id"])
        return "PASS", f"created and deleted memory {memory['id']}"

    def cdk_bootstrap(self) -> Result:
        try:
            stack = self.client("cloudformation").describe_stacks(StackName="CDKToolkit")
        except ClientError:
            return "WARN", f"not bootstrapped; run: cdk bootstrap aws://<account>/{self.region}"
        return "PASS", f"CDKToolkit {stack['Stacks'][0]['StackStatus']}"

    def transaction_search(self) -> Result:
        destination = self.client("xray").get_trace_segment_destination()
        if (
            destination.get("Destination") == "CloudWatchLogs"
            and destination.get("Status") == "ACTIVE"
        ):
            return "PASS", "spans are delivered to CloudWatch Logs"
        return (
            "WARN",
            "not enabled; enable it in CloudWatch > Application Signals > Transaction Search",
        )


def run(name: str, check: Callable[[], Result]) -> str:
    try:
        status, detail = check()
    except (ClientError, BotoCoreError) as error:
        status, detail = "FAIL", str(error)
    print(f"{status:<5} {name:<26} {detail}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--profile", help="AWS profile for the account to check.")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--check-claude", action="store_true")
    parser.add_argument("--probe-memory", action="store_true")
    args = parser.parse_args()

    checks = Checks(boto3.Session(profile_name=args.profile), args.region)
    plan: list[tuple[str, Callable[[], Result]]] = [
        ("Identity", checks.identity),
        ("Organization / SCPs", checks.organization),
        ("Deployment permissions", checks.permissions),
        ("AgentCore quotas", checks.agentcore_quotas),
        ("Bedrock (Amazon Nova)", lambda: checks.bedrock(FIRST_PARTY_MODEL)),
        ("Bedrock (Claude Haiku 5.5)", lambda: checks.bedrock(AGENT_MODEL)),
        ("AgentCore Memory create", checks.memory_probe),
        ("CDK bootstrap", checks.cdk_bootstrap),
        ("Transaction Search", checks.transaction_search),
    ]
    skipped = {
        "Bedrock (Claude Haiku 5.5)": not args.check_claude,
        "AgentCore Memory create": not args.probe_memory,
    }
    statuses = []
    for name, check in plan:
        if skipped.get(name):
            print(f"{'SKIP':<5} {name:<26} enable with --check-claude / --probe-memory")
            continue
        statuses.append(run(name, check))

    verdict = "NOT READY" if "FAIL" in statuses else "READY"
    print(f"\n{verdict} ({statuses.count('FAIL')} failed, {statuses.count('WARN')} warnings)")
    return 1 if verdict == "NOT READY" else 0


if __name__ == "__main__":
    sys.exit(main())
