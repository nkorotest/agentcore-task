# Customer Support Agent on Amazon Bedrock AgentCore

A customer support agent for an online electronics store, built with Strands Agents and Amazon
Bedrock AgentCore. It answers order questions, looks up customers and issues refunds through business
tools exposed by AgentCore Gateway over MCP. A Cedar policy on the gateway, not the prompt, decides
which refunds are allowed.

Deployed in AWS account `536035781966` (`us-east-1`), with Amazon Nova 2 Lite as the model.

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

    runtime -->|Converse| model["Amazon Bedrock<br/>Nova 2 Lite"]
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

Every tool call passes the policy engine before its Lambda runs. Refunds are written with a
conditional put on the idempotency key, so a retried call returns the existing refund.

## Requirements and evidence

| Requirement | Where | Evidence |
|---|---|---|
| Runtime + Strands, picks the right tool | [`SupportAgent/app/support_agent`](SupportAgent/app/support_agent) | [agent scenarios](evidence/scenarios) |
| Gateway with MCP tools (3 business tools) | [`agentcore.json`](SupportAgent/agentcore/agentcore.json), [`backend/`](backend) | [agent and gateway scenarios](evidence/scenarios) |
| Memory across two sessions | [`memory/session.py`](SupportAgent/app/support_agent/memory/session.py), [`request_identity.py`](SupportAgent/app/support_agent/request_identity.py) | [agent scenarios](evidence/scenarios) |
| Identity / IAM, no long-lived credentials | [docs/security.md](docs/security.md) | [least-privilege check](evidence/security/least-privilege.txt) |
| Refund ≤ $1,000 allowed, > $1,000 denied | [`policies/`](SupportAgent/policies) | [scenarios](evidence/scenarios), [traces](evidence/observability) |
| Prompt injection cannot bypass authorization | [docs/security.md](docs/security.md) | [agent scenarios](evidence/scenarios), [trace](evidence/observability) |
| Retry does not create a duplicate refund | [`refunds.py`](backend/src/support_backend/refunds.py) | [operation-123](evidence/reliability/idempotency-operation-123.txt) |
| Retries with exponential backoff, loop protection | [`reliability/`](SupportAgent/app/support_agent/reliability) | Unit tests, [traces](evidence/observability) |
| Observability, failures traceable | [docs/observability.md](docs/observability.md) | [traces](evidence/observability) |

All evidence files: [evidence/README.md](evidence/README.md).

## Repository layout

```
backend/              Tool Lambdas, CDK stacks, tool schemas, unit tests
SupportAgent/         AgentCore project: agentcore.json, agent code, Cedar policies, agent tests
scripts/              Scenario runners, trace viewer, least-privilege check
docs/                 Deployment, security and observability
evidence/             Outputs from runs against the deployed system
```

## Quick start

From the repository root:

```bash
(cd backend && cdk deploy SupportAgentBackend --outputs-file cdk-outputs.json)
(cd SupportAgent && agentcore deploy)
uv run scripts/run_agent_scenarios.py
```

Full steps, tests and teardown: [docs/deployment.md](docs/deployment.md).

## Key decisions

- **The refund limit is a Cedar policy on the gateway**, not a prompt instruction or backend check.
  Amounts are integer cents (Cedar has no decimals), so the rule is `amount_cents <= 100000`.
- **Two kinds of errors.** Bad input and business-rule errors are returned to the model as data and
  never retried. Timeouts and HTTP 5xx fail the Lambda invocation, and the agent retries them with
  backoff.
- **Model:** Amazon Nova 2 Lite. It is set by `MODEL_ID`; the runtime role may invoke only that model.
- **Known limitation:** refunds are not totalled per order, so several refunds under the limit can
  together exceed the order total.
