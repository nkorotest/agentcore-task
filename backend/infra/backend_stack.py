"""Infrastructure for the support agent's business tools.

One Lambda function per Gateway tool, each with its own IAM role, plus the refunds table. Only the
refund function can touch the table, and only with the two actions it uses.
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

LAMBDA_SOURCE_DIR = Path(__file__).resolve().parent.parent / "src"


class SupportBackendStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, fault_injection_enabled: bool, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.refunds_table = dynamodb.TableV2(
            self,
            "RefundsTable",
            partition_key=dynamodb.Attribute(
                name="idempotency_key", type=dynamodb.AttributeType.STRING
            ),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            # Assignment environment: tearing the stack down must not leave billable data behind.
            removal_policy=RemovalPolicy.DESTROY,
        )

        code = lambda_.Code.from_asset(str(LAMBDA_SOURCE_DIR), exclude=["**/__pycache__"])
        environment = {"FAULT_INJECTION_ENABLED": str(fault_injection_enabled).lower()}

        get_order_status = self._tool_function(
            "GetOrderStatus",
            function_name="support-get-order-status",
            handler="support_backend.orders.handler",
            code=code,
            timeout=Duration.seconds(5),
            environment=environment,
        )
        get_customer = self._tool_function(
            "GetCustomer",
            function_name="support-get-customer",
            handler="support_backend.customers.handler",
            code=code,
            timeout=Duration.seconds(5),
            environment=environment,
        )
        refund_customer = self._tool_function(
            "RefundCustomer",
            function_name="support-refund-customer",
            handler="support_backend.refunds.handler",
            code=code,
            timeout=Duration.seconds(10),
            environment={**environment, "REFUNDS_TABLE_NAME": self.refunds_table.table_name},
        )
        self.refunds_table.grant(refund_customer, "dynamodb:PutItem", "dynamodb:GetItem")

        CfnOutput(self, "GetOrderStatusFunctionArn", value=get_order_status.function_arn)
        CfnOutput(self, "GetCustomerFunctionArn", value=get_customer.function_arn)
        CfnOutput(self, "RefundCustomerFunctionArn", value=refund_customer.function_arn)
        CfnOutput(self, "RefundsTableName", value=self.refunds_table.table_name)

    def _tool_function(
        self,
        construct_id: str,
        *,
        function_name: str,
        handler: str,
        code: lambda_.Code,
        timeout: Duration,
        environment: dict[str, str],
    ) -> lambda_.Function:
        log_group = logs.LogGroup(
            self,
            f"{construct_id}Logs",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        return lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler=handler,
            code=code,
            timeout=timeout,
            memory_size=256,
            environment=environment,
            tracing=lambda_.Tracing.ACTIVE,
            logging_format=lambda_.LoggingFormat.JSON,
            application_log_level_v2=lambda_.ApplicationLogLevel.INFO,
            log_group=log_group,
        )
