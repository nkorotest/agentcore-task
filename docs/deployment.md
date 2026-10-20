# Deployment

Run the commands from the repository root.

## Prerequisites

- An AWS account in `us-east-1`, with credentials from `aws login` or IAM Identity Center (no access
  keys needed).
- CloudWatch Transaction Search enabled once per account (CloudWatch → Application Signals →
  Transaction Search).
- Node.js 20+, the AgentCore CLI (`npm install -g @aws/agentcore`), the AWS CDK CLI and `uv`.

## Deploy

1. Business tools:
   ```bash
   (cd backend && cdk bootstrap && cdk deploy SupportAgentBackend --outputs-file cdk-outputs.json)
   ```
2. Agent runtime, memory, gateway, targets and policy engine:
   ```bash
   (cd SupportAgent && agentcore deploy)
   ```
3. Gateway logging and tracing, and the saved Logs Insights queries:
   ```bash
   (cd backend && cdk deploy SupportAgentObservability)
   ```

These values are specific to the account and must be updated in a new one:
- the Lambda ARNs in `agentcore.json`;
- the gateway ARN and account ID in `policies/*.cedar`;
- the account ID in `iam/runtime-bedrock-model-access.json`.

The policies need the gateway's ARN, so in a new account deploy twice: first without the policy
engine, then add it with the new ARN.

## Verify

```bash
uv run scripts/run_scenarios.py          # scenarios directly against the gateway
uv run scripts/run_agent_scenarios.py    # scenarios through the deployed agent
uv run scripts/check_least_privilege.py  # IAM policy simulator checks
```

Talk to the agent. The actor header names the end user, which scopes long-term memory:

```bash
cd SupportAgent
agentcore invoke -H "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id: alice" "Why is my order 123 delayed?"
```

`agentcore dev` runs the same agent locally against the deployed gateway and policy.

## Test

```bash
(cd backend && uv run pytest)
(cd SupportAgent && uv run --project app/support_agent pytest tests)
```

## Tear down

```bash
(cd SupportAgent && agentcore remove all && agentcore deploy)
(cd backend && cdk destroy --all)
```
