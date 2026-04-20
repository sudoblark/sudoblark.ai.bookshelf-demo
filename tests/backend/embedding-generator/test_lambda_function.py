"""Tests for embedding-generator Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/embedding-generator"),
)

RAW_BUCKET = "test-raw-bucket"
TRACKING_TABLE = "test-tracking"

SAMPLE_METADATA = {
    "upload_id": "book-001",
    "title": "The Way of Kings",
    "author": "Brandon Sanderson",
    "description": "A fantasy epic",
    "published_year": 2010,
}

SAMPLE_EMBEDDING = [0.1] * 1536


def _make_bedrock_client(embedding=None):
    """Return a mock Bedrock client that returns the given embedding."""
    mock = MagicMock()
    payload = json.dumps({"embedding": embedding or SAMPLE_EMBEDDING}).encode()
    mock.invoke_model.return_value = {"body": MagicMock(read=lambda: payload)}
    return mock


def _book_key(upload_id="book-001"):
    return f"author=Brandon_Sanderson/published_year=2010/{upload_id}.json"


@pytest.fixture
def aws_with_book(aws_credentials, monkeypatch):
    """S3 + DynamoDB seeded with one book and a SUCCESS tracking record."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)

    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        key = _book_key()
        s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(SAMPLE_METADATA).encode())

        dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
        table = dynamodb.create_table(
            TableName=TRACKING_TABLE,
            KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.put_item(
            Item={
                "upload_id": "book-001",
                "stage": "analysed",
                "stages": {
                    "analysed": {
                        "startedAt": "2024-01-01T00:00:00+00:00",
                        "endedAt": "2024-01-01T00:00:01+00:00",
                        "sourceBucket": RAW_BUCKET,
                        "sourceKey": key,
                        "destinationBucket": RAW_BUCKET,
                        "destinationKey": key,
                    }
                },
            }
        )

        yield s3, dynamodb, table


class TestHandlerSuccess:
    """Test successful embedding generation."""

    def test_returns_upload_id(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["upload_id"] == "book-001"

    def test_returns_embedding_key(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["embedding_key"].endswith(".embedding.json")

    def test_embedding_file_written_to_s3(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        key = _book_key().replace(".json", ".embedding.json")
        obj = s3.get_object(Bucket=RAW_BUCKET, Key=key)
        data = json.loads(obj["Body"].read())
        assert data["upload_id"] == "book-001"
        assert len(data["embedding"]) == len(SAMPLE_EMBEDDING)

    def test_embedding_stage_recorded(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, table = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert "embedding" in record["stages"]

    def test_embedding_stage_status_success(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, table = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert record["stage"] == "embedding"

    def test_uses_description_for_embedding_text(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        bedrock = _make_bedrock_client()
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, bedrock, dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        call_body = json.loads(bedrock.invoke_model.call_args[1]["body"])
        assert "A fantasy epic" in call_body["inputText"]

    def test_falls_back_to_title_author_when_no_description(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        # Overwrite the metadata without a description
        key = _book_key()
        no_desc = {**SAMPLE_METADATA, "description": None}
        s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(no_desc).encode())
        bedrock = _make_bedrock_client()
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, bedrock, dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        call_body = json.loads(bedrock.invoke_model.call_args[1]["body"])
        assert "The Way of Kings" in call_body["inputText"]
        assert "Brandon Sanderson" in call_body["inputText"]

    def test_is_idempotent(self, aws_with_book, monkeypatch):
        """Running twice overwrites the embedding without error."""
        import importlib

        s3, dynamodb, _ = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        mod.handler({"upload_id": "book-001"}, None)
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["upload_id"] == "book-001"


class TestHandlerErrors:
    """Test error handling."""

    def test_missing_upload_id_raises(self, aws_credentials):
        import importlib

        mod = importlib.import_module("lambda_function")
        with pytest.raises(ValueError, match="upload_id is required"):
            mod.handler({}, None)

    def test_unknown_upload_id_raises(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, _ = aws_with_book
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
        with pytest.raises(ValueError, match="No tracking record"):
            mod.handler({"upload_id": "nonexistent"}, None)

    def test_no_analysed_stage_raises(self, aws_credentials, monkeypatch):
        """A tracking record with no ANALYSED stage should raise."""
        import importlib

        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-west-2")
            s3.create_bucket(
                Bucket=RAW_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
            table = dynamodb.create_table(
                TableName=TRACKING_TABLE,
                KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.put_item(Item={"upload_id": "book-001", "stage": "queued", "stages": {}})
            mod = importlib.import_module("lambda_function")
            monkeypatch.setattr(mod, "_get_clients", lambda: (s3, _make_bedrock_client(), dynamodb))
            with pytest.raises(ValueError, match="No completed ANALYSED stage"):
                mod.handler({"upload_id": "book-001"}, None)

    def test_bedrock_failure_raises_and_records_failed_stage(self, aws_with_book, monkeypatch):
        import importlib

        s3, dynamodb, table = aws_with_book
        failing_bedrock = MagicMock()
        failing_bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        mod = importlib.import_module("lambda_function")
        monkeypatch.setattr(mod, "_get_clients", lambda: (s3, failing_bedrock, dynamodb))
        with pytest.raises(RuntimeError, match="Embedding generation failed"):
            mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert record["stage"] == "failed"
        assert "error" in record["stages"]["embedding"]
