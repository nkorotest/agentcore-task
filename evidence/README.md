# Evidence

Raw outputs from runs against the deployed system in account `062788795353`, region `us-east-1`.
Each file records the command that produced it.

| File | Shows |
|---|---|
| [scenarios/gateway-*.json](scenarios) | Every required scenario that goes through the gateway: order and customer lookups, refunds at and over the limit, the prompt-injection refund, the `operation-123` retry, and the three failures |
| [reliability/idempotency-operation-123.txt](reliability/idempotency-operation-123.txt) | First run of `operation-123`: two identical calls return one `refund_id`, the second with `replayed: true`; the refund Lambda logs one "Refund created" and one "Refund replayed" |
| [security/least-privilege.txt](security/least-privilege.txt) | IAM policy simulator results for every deployed role (18 checks, all pass) |
| [observability/*-call.txt](observability) | The tool call that triggered each failure, with the client's view of the result |
| [observability/*-trace.txt](observability) | The trace timeline for each failure: spans and gateway log entries on one trace ID |

Scenarios that need the agent runtime or a model (agent conversations, memory across sessions,
prompt injection through the model, wrong tool selection, the LLM loop) are pending the account's
AgentCore and Bedrock quotas.
