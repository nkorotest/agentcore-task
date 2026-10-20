// IAM callers from this AWS account may issue refunds of up to and including $1,000.00
// (100000 cents). Larger refunds match no permit policy, so the policy engine denies them before
// the refund Lambda is invoked, whatever the model was told or decided.
permit (
  principal is AgentCore::IamEntity,
  action == AgentCore::Action::"RefundsTarget___refund_customer",
  resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:062788795353:gateway/supportagent-supportgateway-igxisl7sc6"
)
when {
  principal.id like "arn:aws:*::062788795353:*" &&
  context.input.amount_cents <= 100000
};
