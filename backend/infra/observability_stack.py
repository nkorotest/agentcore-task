"""Observability for the AgentCore Gateway and the tool Lambdas.

AgentCore does not configure gateway logging itself, so this stack delivers the gateway's
application logs to CloudWatch Logs and its traces to X-Ray (Transaction Search), and saves the
Logs Insights queries used to investigate tool failures.
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_logs as logs
from constructs import Construct

TOOL_LOG_GROUPS = [
    "/aws/lambda/support-get-order-status",
    "/aws/lambda/support-get-customer",
    "/aws/lambda/support-refund-customer",
]


class SupportObservabilityStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, gateway_arn: str, gateway_id: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        gateway_log_group = logs.LogGroup(
            self,
            "GatewayApplicationLogs",
            log_group_name=f"/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway_id}",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self._deliver(
            "GatewayLogs",
            gateway_arn=gateway_arn,
            name=f"{gateway_id}-logs",
            log_type="APPLICATION_LOGS",
            destination=logs.CfnDeliveryDestination(
                self,
                "GatewayLogsDestination",
                name=f"{gateway_id}-logs",
                destination_resource_arn=gateway_log_group.log_group_arn,
            ),
        )
        self._deliver(
            "GatewayTraces",
            gateway_arn=gateway_arn,
            name=f"{gateway_id}-traces",
            log_type="TRACES",
            destination=logs.CfnDeliveryDestination(
                self,
                "GatewayTracesDestination",
                name=f"{gateway_id}-traces",
                delivery_destination_type="XRAY",
            ),
        )

        self._query(
            "ToolErrors",
            "support-agent/tool-errors",
            TOOL_LOG_GROUPS,
            "fields @timestamp, tool, level, message, error_code, error_message,"
            " gateway_request_id, requestId"
            " | filter level in ['WARNING', 'ERROR']"
            " | sort @timestamp desc",
        )
        self._query(
            "ToolTimeouts",
            "support-agent/tool-timeouts",
            TOOL_LOG_GROUPS,
            "fields @timestamp, @log, record.requestId, record.metrics.durationMs"
            " | filter type = 'platform.report' and record.status = 'timeout'"
            " | sort @timestamp desc",
        )
        self._query(
            "ToolCallsByGatewayRequest",
            "support-agent/tool-calls-by-gateway-request",
            TOOL_LOG_GROUPS,
            "fields @timestamp, tool, message, error_code, mcp_message_id, requestId"
            " | filter ispresent(gateway_request_id)"
            " | sort @timestamp desc"
            " | display @timestamp, gateway_request_id, tool, message, error_code, requestId",
        )
        self._query(
            "RefundIdempotency",
            "support-agent/refund-idempotency",
            ["/aws/lambda/support-refund-customer"],
            "fields @timestamp, message, idempotency_key, refund_id"
            " | filter message like /Refund (created|replayed)/"
            " | sort @timestamp desc",
        )
        self._query(
            "GatewayLog",
            "support-agent/gateway-log",
            [gateway_log_group.log_group_name],
            "fields @timestamp, @message | sort @timestamp desc | limit 100",
        )

    def _deliver(
        self,
        construct_id: str,
        *,
        gateway_arn: str,
        name: str,
        log_type: str,
        destination: logs.CfnDeliveryDestination,
    ) -> None:
        source = logs.CfnDeliverySource(
            self, f"{construct_id}Source", name=name, log_type=log_type, resource_arn=gateway_arn
        )
        delivery = logs.CfnDelivery(
            self,
            f"{construct_id}Delivery",
            delivery_source_name=source.name,
            delivery_destination_arn=destination.attr_arn,
        )
        delivery.node.add_dependency(source)

    def _query(self, construct_id: str, name: str, log_group_names: list[str], query: str) -> None:
        logs.CfnQueryDefinition(
            self,
            construct_id,
            name=name,
            log_group_names=log_group_names,
            query_string=query,
        )
