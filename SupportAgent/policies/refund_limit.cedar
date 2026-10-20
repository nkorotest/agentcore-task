// Refunds up to $1,000.00 (100000 cents); anything larger is denied by default.
permit (
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"RefundsTarget___refund_customer",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:536035781966:gateway/supportagent-supportgateway-v0etrfiz7f"
)
when {
  principal.id like "arn:aws:*::536035781966:*" &&
  context.input.amount_cents <= 100000
};
