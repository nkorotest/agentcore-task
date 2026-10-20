import boto3
import pytest
from moto import mock_aws

from support_backend import refunds

REFUNDS_TABLE_NAME = "refunds-test"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Keep tests off real AWS accounts and start every test with fault injection disabled."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("FAULT_INJECTION_ENABLED", "false")


@pytest.fixture
def fault_injection(monkeypatch):
    monkeypatch.setenv("FAULT_INJECTION_ENABLED", "true")


@pytest.fixture
def refunds_table(monkeypatch):
    with mock_aws():
        table = boto3.resource("dynamodb").create_table(
            TableName=REFUNDS_TABLE_NAME,
            KeySchema=[{"AttributeName": "idempotency_key", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "idempotency_key", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        monkeypatch.setenv("REFUNDS_TABLE_NAME", REFUNDS_TABLE_NAME)
        refunds._refunds_table.cache_clear()
        yield table
        refunds._refunds_table.cache_clear()
