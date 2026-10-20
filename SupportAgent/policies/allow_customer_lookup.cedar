// IAM callers from this AWS account (the agent's runtime role, developers) may look up customers.
permit (
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"CustomersTarget___get_customer",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:062788795353:gateway/supportagent-supportgateway-igxisl7sc6"
)
when { principal.id like "arn:aws:*::062788795353:*" };
