"""Tests for raw-to-processed-copy Lambda handler."""

import importlib.util
import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

# Add application/backend/ to sys.path so `import common` resolves inside the Lambda.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend"),
)

_LAMBDA_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../application/backend/raw-to-processed-copy/lambda_function.py",
    )
)


def _load_module():
    """Load the Lambda module via file path to avoid module name collisions."""
    spec = importlib.util.spec_from_file_location("raw_to_processed_copy_lf", _LAMBDA_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RAW_BUCKET = "test-raw-bucket"
PROCESSED_BUCKET = "test-processed-bucket"
TRACKING_TABLE = "test-tracking-r2p"

SAMPLE_METADATA = {
    "upload_id": "book-001",
    "title": "Guards! Guards!",
    "author": "Terry Pratchett",
    "description": "The first appearance of Sam Vimes and the Night Watch",
    "published_year": 1989,
}

BOOK_KEY = "author=Terry_Pratchett/published_year=1989/book-001.json"


@pytest.fixture
def aws_with_book(aws_credentials, monkeypatch):
    """S3 (raw + processed) + DynamoDB seeded with one analysed book."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    monkeypatch.setenv("PROCESSED_BUCKET", PROCESSED_BUCKET)
    monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)

    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        for bucket in (RAW_BUCKET, PROCESSED_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )

        s3.put_object(Bucket=RAW_BUCKET, Key=BOOK_KEY, Body=json.dumps(SAMPLE_METADATA).encode())

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
                        "sourceKey": BOOK_KEY,
                        "destinationBucket": RAW_BUCKET,
                        "destinationKey": BOOK_KEY,
                    }
                },
            }
        )

        yield s3, dynamodb, table


class TestHandlerSuccess:
    """Test successful copy from raw to processed."""

    def test_returns_upload_id(self, aws_with_book):
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["upload_id"] == "book-001"

    def test_returns_processed_key(self, aws_with_book):
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["processed_key"] == BOOK_KEY

    def test_file_written_to_processed_bucket(self, aws_with_book):
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        mod.handler({"upload_id": "book-001"}, None)
        obj = s3.get_object(Bucket=PROCESSED_BUCKET, Key=BOOK_KEY)
        data = json.loads(obj["Body"].read())
        assert data["upload_id"] == "book-001"

    def test_processed_stage_recorded(self, aws_with_book):
        s3, dynamodb, table = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert "processed" in record["stages"]

    def test_stage_field_set_to_processed(self, aws_with_book):
        s3, dynamodb, table = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert record["stage"] == "processed"

    def test_processed_stage_has_destination_key(self, aws_with_book):
        s3, dynamodb, table = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        mod.handler({"upload_id": "book-001"}, None)
        record = table.get_item(Key={"upload_id": "book-001"})["Item"]
        assert record["stages"]["processed"]["destinationKey"] == BOOK_KEY

    def test_is_idempotent(self, aws_with_book):
        """Running twice overwrites the processed file without error."""
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        mod.handler({"upload_id": "book-001"}, None)
        result = mod.handler({"upload_id": "book-001"}, None)
        assert result["upload_id"] == "book-001"


class TestHandlerErrors:
    """Test error handling."""

    def test_missing_upload_id_raises(self, aws_with_book):
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        with pytest.raises(ValueError, match="upload_id is required"):
            mod.handler({}, None)

    def test_unknown_upload_id_raises(self, aws_with_book):
        s3, dynamodb, _ = aws_with_book
        mod = _load_module()
        mod._processor = mod.RawToProcessedCopyProcessor(s3_client=s3, dynamodb_resource=dynamodb)
        with pytest.raises(ValueError, match="No tracking record"):
            mod.handler({"upload_id": "nonexistent"}, None)

    def test_no_analysed_stage_raises(self, aws_credentials, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        monkeypatch.setenv("PROCESSED_BUCKET", PROCESSED_BUCKET)
        monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-west-2")
            for bucket in (RAW_BUCKET, PROCESSED_BUCKET):
                s3.create_bucket(
                    Bucket=bucket,
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
            mod = _load_module()
            mod._processor = mod.RawToProcessedCopyProcessor(
                s3_client=s3, dynamodb_resource=dynamodb
            )
            with pytest.raises(ValueError, match="No completed ANALYSED stage"):
                mod.handler({"upload_id": "book-001"}, None)
