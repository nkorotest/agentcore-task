import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infra.backend_stack import SupportBackendStack


@pytest.fixture(scope="module")
def template():
    stack = SupportBackendStack(cdk.App(), "TestBackend", fault_injection_enabled=False)
    return Template.from_stack(stack)


def _actions(statement):
    actions = statement["Action"]
    return [actions] if isinstance(actions, str) else actions


def test_each_tool_has_its_own_traced_function(template):
    template.resource_count_is("AWS::Lambda::Function", 3)
    template.resource_count_is("AWS::IAM::Role", 3)
    template.all_resources_properties(
        "AWS::Lambda::Function", {"TracingConfig": {"Mode": "Active"}}
    )


def test_only_the_refund_function_can_access_the_refunds_table(template):
    dynamodb_grants = [
        (policy_id, statement)
        for policy_id, policy in template.find_resources("AWS::IAM::Policy").items()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        if any(action.startswith("dynamodb:") for action in _actions(statement))
    ]

    assert len(dynamodb_grants) == 1
    policy_id, statement = dynamodb_grants[0]
    assert policy_id.startswith("RefundCustomer")
    assert sorted(_actions(statement)) == ["dynamodb:GetItem", "dynamodb:PutItem"]
