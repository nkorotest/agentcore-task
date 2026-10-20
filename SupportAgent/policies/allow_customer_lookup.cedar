// IAM callers from this AWS account (the agent's runtime role, developers) may look up customers.
permit (
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"CustomersTarget___get_customer",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:536035781966:gateway/supportagent-supportgateway-v0etrfiz7f"
)
when { principal.id like "arn:aws:*::536035781966:*" };
