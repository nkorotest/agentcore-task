# Customer Support Agent on Amazon Bedrock AgentCore

A customer support agent for an online electronics store, built with Strands Agents and Amazon
Bedrock AgentCore. It answers order questions, looks up customers and issues refunds through business
tools exposed by AgentCore Gateway over MCP. A Cedar policy on the gateway, not the prompt, decides
which refunds are allowed.

## Current status

| Part | Status |
|---|---|
| Business tools (Lambda + DynamoDB) | Deployed and verified |
| AgentCore Gateway (MCP, IAM auth) | Deployed and verified |
| AgentCore Policy (Cedar, ENFORCE) | Deployed and verified |
| Observability (traces, gateway and Lambda logs, saved queries) | Deployed and verified for the gateway-level failures |
| Agent code (Strands, retries, loop guard, memory wiring) | Written and unit-tested |
| AgentCore Runtime and Memory | **Not deployed yet** |

The AWS account used for this project currently has its AgentCore Runtime and Memory quotas set to 0
and Bedrock model invocation blocked, pending AWS Support. Everything that does not need those
services is deployed and tested. See [Deploying the runtime and memory](#deploying-the-runtime-and-memory)
for the remaining steps.

## Architecture

```mermaid
flowchart LR
    caller([Support app / customer]) -->|InvokeAgentRuntime, SigV4| runtime

    subgraph AgentCore
        runtime["AgentCore Runtime<br/>Strands agent<br/>ToolRetry + LoopGuard hooks"]
        memory[("AgentCore Memory<br/>user preferences")]
        gateway["AgentCore Gateway<br/>MCP, AWS_IAM inbound auth"]
        policy{{"Policy Engine<br/>Cedar, ENFORCE"}}
    end

    runtime -->|Converse| model["Amazon Bedrock<br/>Claude Haiku"]
    runtime <-->|events, preferences| memory
    runtime -->|"tools/call (SigV4, runtime role)"| gateway
    gateway -->|authorize every call| policy
    gateway -->|"ALLOW only (gateway role)"| orders["λ get_order_status"]
    gateway --> customers["λ get_customer"]
    gateway --> refunds["λ refund_customer"]
    refunds -->|"conditional PutItem<br/>key = idempotency_key"| table[("DynamoDB<br/>refunds")]

    runtime -.->|OTel spans, logs| cw["CloudWatch<br/>Transaction Search + Logs"]
    gateway -.->|logs, policy decisions| cw
    orders -.-> cw
    customers -.-> cw
    refunds -.-> cw
```

A refund request flows like this: the model calls `refund_customer` through the gateway, the policy
engine evaluates the call, and only an ALLOW reaches the Lambda. The Lambda writes the refund with a
conditional put keyed on the idempotency key, so a retried call returns the existing refund.

## Requirements and evidence

| Requirement | Where | Evidence |
|---|---|---|
| Runtime + Strands | [`SupportAgent/app/support_agent`](SupportAgent/app/support_agent) | Pending runtime quota |
| Gateway with MCP tools (3 business tools) | [`agentcore.json`](SupportAgent/agentcore/agentcore.json), [`backend/`](backend) | [scenarios](evidence/scenarios) |
| Memory across two sessions | [`memory/session.py`](SupportAgent/app/support_agent/memory/session.py) | Pending memory quota |
| Identity / IAM, no long-lived credentials | [docs/security.md](docs/security.md) | [least-privilege check](evidence/security/least-privilege.txt) |
| Refund ≤ $1,000 allowed, > $1,000 denied | [`policies/`](SupportAgent/policies) | [scenarios](evidence/scenarios), [deny trace](evidence/observability/policy-deny-trace.txt) |
| Prompt injection cannot bypass authorization | [docs/security.md](docs/security.md) | [scenarios](evidence/scenarios), [deny trace](evidence/observability/policy-deny-trace.txt); agent run pending model |
| Retry does not create a duplicate refund | [`refunds.py`](backend/src/support_backend/refunds.py) | [operation-123](evidence/reliability/idempotency-operation-123.txt) |
| Retries with exponential backoff | [`reliability/`](SupportAgent/app/support_agent/reliability) | Unit tests |
| Observability, failures traceable | [docs/observability.md](docs/observability.md) | [traces](evidence/observability) |

The full list of evidence files is in [evidence/README.md](evidence/README.md).

## Repository layout

```
backend/              Business tools: Lambda handlers, CDK stacks, tool schemas, unit tests
SupportAgent/         AgentCore project (agentcore CLI)
  agentcore/          agentcore.json: runtime, gateway, targets, policy engine
  app/support_agent/  The Strands agent (runtime code)
  policies/           Cedar policies
  iam/                Extra IAM policy for the runtime role
  tests/              Agent unit tests
scripts/              Gateway client, scenario runner, trace viewer, least-privilege check
docs/                 Security and observability write-ups
evidence/             Outputs from runs against the deployed system
```

## Deploy

Prerequisites: an AWS account in `us-east-1` with CDK bootstrapped, Node.js 20+, the AgentCore CLI
(`npm install -g @aws/agentcore`), the AWS CDK CLI, `uv`, and AWS credentials from `aws login` or IAM
Identity Center. No access keys are needed.

1. Deploy the business tools:
   ```bash
   cd backend
   cdk deploy SupportAgentBackend --outputs-file cdk-outputs.json
   ```
2. Deploy the gateway, its targets and the policy engine:
   ```bash
   cd SupportAgent
   agentcore deploy
   ```
   The Lambda ARNs in `agentcore.json` and the gateway ARN in `policies/*.cedar` are specific to this
   account. In a new account, update them: deploy once without the policies, then add the policies
   with the new gateway ARN and deploy again.
3. Deploy gateway logging, tracing and the saved Logs Insights queries:
   ```bash
   cd backend
   cdk deploy SupportAgentObservability
   ```
4. Verify:
   ```bash
   uv run scripts/run_scenarios.py
   uv run scripts/check_least_privilege.py
   ```

## Test

```bash
cd backend && uv run pytest
cd SupportAgent && uv run --project app/support_agent pytest tests
```

## Run the agent locally

`agentcore dev` runs the agent on your machine against the deployed gateway and policy. By default
it uses Bedrock. While Bedrock is unavailable, it can use the Anthropic API instead. Add these lines
to the git-ignored `SupportAgent/agentcore/.env.local`:

```
MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=<your key>
```

Name the end user in the actor header; long-term memory is scoped to it:

```bash
agentcore dev -H "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id: alice" "Why is my order 123 delayed?"
```

## Deploying the runtime and memory

Once the account's AgentCore quotas are raised:

1. Add the runtime back to `runtimes` in [`agentcore.json`](SupportAgent/agentcore/agentcore.json):
   ```json
   {
     "name": "support_agent",
     "build": "CodeZip",
     "entrypoint": "main.py",
     "codeLocation": "app/support_agent/",
     "runtimeVersion": "PYTHON_3_14",
     "networkMode": "PUBLIC",
     "protocol": "HTTP",
     "requestHeaderAllowlist": ["X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id"],
     "additionalPolicies": ["../../iam/runtime-bedrock-model-access.json"]
   }
   ```
2. Add the memory, then deploy:
   ```bash
   agentcore add memory --name support_agentMemory --strategies USER_PREFERENCE
   agentcore deploy
   ```

## Tear down

```bash
cd SupportAgent && agentcore remove all && agentcore deploy
cd backend && cdk destroy --all
```

## Design notes

- **Money is integer cents.** Cedar has no decimal type, so the refund limit is
  `context.input.amount_cents <= 100000`.
- **The refund limit lives only in the Cedar policy.** The backend checks that a refund does not exceed
  the order total, but it does not duplicate the $1,000 rule. The system prompt does not mention the
  rule either.
- **Errors come in two kinds.** Bad input and business-rule errors are returned to the model as data,
  and are never retried. Failures such as timeouts and HTTP 5xx fail the Lambda invocation, so the
  gateway reports `isError: true` and the agent retries them with backoff.
- **Known limitation:** refunds are not totalled per order, so several refunds under the limit can
  together exceed the order total.
