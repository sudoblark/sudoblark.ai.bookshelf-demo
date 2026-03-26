"""Tests for file-router Lambda function."""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from common.tracker import BookshelfTracker, StageStatus, UploadStage, UploadStatus
from moto import mock_aws

# Dynamically import lambda_function from file-router directory
spec = importlib.util.spec_from_file_location(
    "file_router_lambda_function",
    os.path.join(os.path.dirname(__file__), "../lambda-packages/file-router/lambda_function.py"),
)
file_router_lambda = importlib.util.module_from_spec(spec)
sys.modules["file_router_lambda_function"] = file_router_lambda
spec.loader.exec_module(file_router_lambda)

LANDING_BUCKET = "aws-sudoblark-development-bookshelf-demo-landing"
RAW_BUCKET = "aws-sudoblark-development-bookshelf-demo-raw"
TRACKING_TABLE = "test-tracking"
REGION = "eu-west-2"


def _make_s3_event(bucket: str, key: str) -> dict:
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": bucket, "arn": f"arn:aws:s3:::{bucket}"},
                    "object": {"key": key, "size": 100},
                },
            }
        ]
    }


class TestFileRouterHandlerInit:
    def test_initialises_with_raw_bucket_set(self, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        h = file_router_lambda.FileRouterHandler()
        assert h._raw_bucket_tier == "raw"

    def test_raises_when_raw_bucket_missing(self, monkeypatch):
        monkeypatch.delenv("RAW_BUCKET", raising=False)
        with pytest.raises(ValueError, match="RAW_BUCKET environment variable is required"):
            file_router_lambda.FileRouterHandler()

    def test_raises_when_tracking_table_missing(self, monkeypatch):
        monkeypatch.delenv("TRACKING_TABLE", raising=False)
        with pytest.raises(ValueError, match="TRACKING_TABLE environment variable is required"):
            file_router_lambda.FileRouterHandler()


class TestParseUploadKey:
    def test_parses_valid_key(self):
        user_id, upload_id, filename = file_router_lambda.parse_upload_key(
            "uploads/default/test-upload/cover.jpg"
        )
        assert user_id == "default"
        assert upload_id == "test-upload"
        assert filename == "cover.jpg"

    def test_raises_for_too_shallow_key(self):
        with pytest.raises(ValueError, match="expected format"):
            file_router_lambda.parse_upload_key("uploads/default/cover.jpg")

    def test_raises_for_missing_uploads_prefix(self):
        with pytest.raises(ValueError, match="expected format"):
            file_router_lambda.parse_upload_key("archive/default/upload1/cover.jpg")

    def test_raises_for_flat_key(self):
        with pytest.raises(ValueError, match="expected format"):
            file_router_lambda.parse_upload_key("cover.jpg")


class TestIsSupportedExtension:
    def test_jpg_is_supported(self):
        assert file_router_lambda.is_supported_extension("cover.jpg") is True

    def test_jpeg_is_supported(self):
        assert file_router_lambda.is_supported_extension("cover.jpeg") is True

    def test_png_is_supported(self):
        assert file_router_lambda.is_supported_extension("cover.png") is True

    def test_zip_is_not_supported(self):
        assert file_router_lambda.is_supported_extension("archive.zip") is False

    def test_pdf_is_not_supported(self):
        assert file_router_lambda.is_supported_extension("book.pdf") is False

    def test_case_insensitive(self):
        assert file_router_lambda.is_supported_extension("cover.JPG") is True


class TestHandler:
    @mock_aws
    def test_copies_file_to_raw_bucket(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        monkeypatch.setattr(file_router_lambda.handler, "_tracker", MagicMock())

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        result = file_router_lambda.handler(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        assert result["statusCode"] == 200
        assert result["processed_count"] == 1
        assert key in result["processed_files"]

        obj = s3.get_object(Bucket=RAW_BUCKET, Key=key)
        assert obj["Body"].read() == b"imgdata"

    @mock_aws
    def test_deletes_source_after_copy(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        monkeypatch.setattr(file_router_lambda.handler, "_tracker", MagicMock())

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        file_router_lambda.handler(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        objects = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix="uploads/")
        assert objects.get("KeyCount", 0) == 0

    @mock_aws
    def test_rejects_unsupported_extension(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        monkeypatch.setattr(file_router_lambda.handler, "_tracker", MagicMock())

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/archive.zip"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"zip")

        result = file_router_lambda.handler(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        assert result["statusCode"] == 207
        assert result["failed_count"] == 1
        assert "Unsupported" in result["failed_files"][0]["error"]

    @mock_aws
    def test_rejects_path_traversal_key(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        monkeypatch.setattr(file_router_lambda.handler, "_tracker", MagicMock())

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        event = _make_s3_event(LANDING_BUCKET, "uploads/../secret/file.jpg")
        result = file_router_lambda.handler(event, lambda_context)

        assert result["statusCode"] == 207
        assert result["failed_count"] == 1
        assert "path traversal" in result["failed_files"][0]["error"]

    @mock_aws
    def test_rejects_invalid_key_format(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        monkeypatch.setattr(file_router_lambda.handler, "_tracker", MagicMock())

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        event = _make_s3_event(LANDING_BUCKET, "cover.jpg")
        result = file_router_lambda.handler(event, lambda_context)

        assert result["statusCode"] == 207
        assert result["failed_count"] == 1
        assert "expected format" in result["failed_files"][0]["error"]


def _create_tracking_table(resource):
    resource.create_table(
        TableName=TRACKING_TABLE,
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "file_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "file_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


class TestHandlerWithTracking:
    @mock_aws
    def test_records_success_stage_on_routing(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        key = "uploads/user-1/upload-1/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        _create_tracking_table(dynamodb)

        tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=TRACKING_TABLE)
        h = file_router_lambda.FileRouterHandler(s3_client=s3, tracker=tracker)

        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)
        assert result["statusCode"] == 200

        item = (
            dynamodb.Table(TRACKING_TABLE)
            .get_item(Key={"user_id": "user-1", "file_id": "upload-1#cover.jpg"})
            .get("Item")
        )
        assert item["current_status"] == UploadStatus.SUCCESS.value
        assert len(item["stage_progress"]) == 1
        entry = item["stage_progress"][0]
        assert entry["stage_name"] == UploadStage.ROUTING.value
        assert entry["status"] == StageStatus.SUCCESS.value
        assert entry["source"] == {"bucket": LANDING_BUCKET, "key": key}
        assert entry["destination"] == {"bucket": RAW_BUCKET, "key": key}

    @mock_aws
    def test_records_failed_stage_on_copy_error(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")

        s3 = MagicMock()
        s3.copy_object.side_effect = Exception("S3 unavailable")

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        _create_tracking_table(dynamodb)

        tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=TRACKING_TABLE)
        h = file_router_lambda.FileRouterHandler(s3_client=s3, tracker=tracker)

        key = "uploads/user-1/upload-1/cover.jpg"
        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)
        assert result["statusCode"] == 207

        item = (
            dynamodb.Table(TRACKING_TABLE)
            .get_item(Key={"user_id": "user-1", "file_id": "upload-1#cover.jpg"})
            .get("Item")
        )
        assert item["current_status"] == UploadStatus.FAILED.value
        assert item["stage_progress"][0]["status"] == StageStatus.FAILED.value
        assert item["stage_progress"][0]["error_message"] == "S3 unavailable"
