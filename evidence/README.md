# Evidence

Raw outputs from runs against the deployed system in AWS account `536035781966`, region `us-east-1`.
Each file records the command that produced it.

| File | Shows |
|---|---|
| `scenarios/agent-*.json` | Every required scenario through the deployed agent on AgentCore Runtime. Each turn has its prompt, actor, session, trace ID, the tools the model called with their arguments, and the answer. The last run uses the final system prompt; the earlier run is the one the failure traces below come from |
| `scenarios/gateway-*.json` | The same requirements checked directly at the gateway, with no model: lookups, refunds at and over the limit, the prompt-injection refund, the `operation-123` retry, and three failures |
| [reliability/idempotency-operation-123.txt](reliability/idempotency-operation-123.txt) | `operation-123` sent twice: one `refund_id`, the second call `replayed: true`; one refund row; one "Refund created" and one "Refund replayed" log line |
| [security/least-privilege.txt](security/least-privilege.txt) | IAM policy simulator results for the runtime, gateway and Lambda roles (25 checks, all pass) |
| `observability/*-trace.txt` | End-to-end trace timelines (agent spans, gateway spans and log entries, Lambda spans) for a healthy request, memory recall, the policy denial, and the five failure scenarios. See [docs/observability.md](../docs/observability.md) |

To regenerate:

```bash
uv run scripts/run_agent_scenarios.py
uv run scripts/run_scenarios.py
uv run scripts/check_least_privilege.py
uv run scripts/show_trace.py <trace-id>
```
