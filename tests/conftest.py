"""Shared pytest fixtures for Lambda function tests."""

import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock

# Add lambda-packages/ to sys.path so `import common` resolves when Lambda
# modules are loaded dynamically via importlib.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../lambda-packages"),
)

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402

# Set AWS credentials BEFORE importing boto3 to prevent region errors
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-2"
os.environ["LOG_LEVEL"] = "INFO"
# Required by FileRouterHandler and MetadataExtractorHandler at module-load time
os.environ["RAW_BUCKET"] = "raw"
os.environ["PROCESSED_BUCKET"] = "processed"
os.environ["TRACKING_TABLE"] = "test-tracking"


@pytest.fixture
def aws_credentials(monkeypatch):
    """Mock AWS credentials for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


@pytest.fixture
def s3_client(aws_credentials):
    """Create mock S3 client."""
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-2")
        yield client


@pytest.fixture
def lambda_context():
    """Create mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = "arn:aws:lambda:eu-west-2:123456789012:function:test-function"
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def sample_s3_event() -> Dict[str, Any]:
    """Create sample S3 event for testing."""
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket", "arn": "arn:aws:s3:::test-bucket"},
                    "object": {"key": "test-file.zip", "size": 1024},
                },
            }
        ]
    }
