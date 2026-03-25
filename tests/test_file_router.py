"""Tests for file-router Lambda function."""

import importlib.util
import os
import sys

import boto3
import pytest
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


class TestGetConfig:
    def test_returns_config_when_raw_bucket_set(self, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", "raw")
        config = file_router_lambda.get_config()
        assert config["raw_bucket"] == "raw"

    def test_raises_when_raw_bucket_missing(self, monkeypatch):
        monkeypatch.delenv("RAW_BUCKET", raising=False)
        with pytest.raises(ValueError, match="RAW_BUCKET environment variable is required"):
            file_router_lambda.get_config()


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


class TestResolveRawBucket:
    def test_resolves_correctly(self):
        result = file_router_lambda.resolve_raw_bucket(
            "aws-sudoblark-development-bookshelf-demo-landing", "raw"
        )
        assert result == "aws-sudoblark-development-bookshelf-demo-raw"

    def test_raises_for_short_bucket_name(self):
        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            file_router_lambda.resolve_raw_bucket("bad-name", "raw")


class TestHandler:
    @mock_aws
    def test_copies_file_to_raw_bucket(self, monkeypatch, lambda_context):
        monkeypatch.setenv("RAW_BUCKET", "raw")

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
