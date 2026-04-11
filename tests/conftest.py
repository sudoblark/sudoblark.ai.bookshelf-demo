"""Shared pytest fixtures for Lambda function tests."""

import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock

# Add application/backend/ to sys.path so `import common` resolves when Lambda
# modules are loaded dynamically via importlib.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../application/backend"),
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
# Required by Lambda handlers at module-load time
os.environ["DATA_LAKE_PREFIX"] = "aws-sudoblark-development-bookshelf-demo"
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
                    "bucket": {
                        "name": "test-bucket",
                        "arn": "arn:aws:s3:::test-bucket",
                    },
                    "object": {"key": "test-file.zip", "size": 1024},
                },
            }
        ]
    }


# ============================================================================
# streaming-agent fixtures
# ============================================================================


@pytest.fixture
def mock_s3_presigned_client():
    """Mock S3 client for presigned URL generation."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = (
        "https://test-bucket.s3.amazonaws.com/presigned-url"
    )
    return mock_client


@pytest.fixture
def mock_textract_client():
    """Mock Textract client with sample detect_document_text response."""
    mock = MagicMock()
    mock.detect_document_text.return_value = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "Sample Book Title",
                "Confidence": 99.5,
            },
            {
                "BlockType": "LINE",
                "Text": "Author Name",
                "Confidence": 98.2,
            },
        ]
    }
    return mock


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock runtime client for agent testing."""
    return MagicMock()


@pytest.fixture
def sample_metadata() -> Dict[str, Any]:
    """Sample book metadata for testing accept_handler."""
    return {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "publisher": "Scribner",
        "published_year": 2004,
        "description": "A classic American novel",
        "confidence": 0.95,
    }


@pytest.fixture
def google_books_response() -> Dict[str, Any]:
    """Sample Google Books API response."""
    return {
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "Test Book",
                    "authors": ["Test Author"],
                    "publisher": "Test Publisher",
                    "publishedDate": "2020",
                    "description": "Test description",
                }
            }
        ],
    }


@pytest.fixture
def openlibrary_response() -> Dict[str, Any]:
    """Sample Open Library API response."""
    return {
        "title": "Test Book",
        "authors": [{"name": "Test Author"}],
        "publishers": ["Test Publisher"],
        "publish_date": "2020",
        "description": "Test description",
    }


@pytest.fixture
def mock_fastapi_request():
    """Create a mock FastAPI Request with query params and body."""
    from fastapi import Request

    request = MagicMock(spec=Request)
    request.query_params = {}

    async def json_mock():
        return {}

    request.json = json_mock
    return request


@pytest.fixture
def sse_parser():
    """Parse SSE event stream into list of events."""
    import json

    def parse(stream_data: str) -> list:
        events = []
        for line in stream_data.strip().split("\n\n"):
            if line.startswith("data: "):
                json_str = line[6:]  # Remove "data: " prefix
                events.append(json.loads(json_str))
        return events

    return parse
