"""Tests for unzip-processor Lambda function."""

import importlib.util
import io
import os

# Add lambda-packages to path for imports
import sys
import zipfile
from unittest.mock import patch

import pytest

# Dynamically import lambda_function from unzip-processor directory
spec = importlib.util.spec_from_file_location(
    "unzip_lambda_function",
    os.path.join(
        os.path.dirname(__file__), "../lambda-packages/unzip-processor/lambda_function.py"
    ),
)
unzip_lambda = importlib.util.module_from_spec(spec)
sys.modules["unzip_lambda_function"] = unzip_lambda
spec.loader.exec_module(unzip_lambda)


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_success(self, monkeypatch):
        """Should return config when RAW_BUCKET is set."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = unzip_lambda.get_config()

        assert config["raw_bucket"] == "test-raw-bucket"
        assert config["log_level"] == "INFO"

    def test_get_config_missing_raw_bucket(self, monkeypatch):
        """Should raise ValueError when RAW_BUCKET is missing."""
        monkeypatch.delenv("RAW_BUCKET", raising=False)

        with pytest.raises(ValueError, match="RAW_BUCKET environment variable is required"):
            unzip_lambda.get_config()

    def test_get_config_default_log_level(self, monkeypatch):
        """Should use default log level when not specified."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        config = unzip_lambda.get_config()

        assert config["log_level"] == "INFO"

    def test_get_config_invalid_log_level(self, monkeypatch):
        """Should raise ValueError for invalid log level."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            unzip_lambda.get_config()


class TestGetContentType:
    """Tests for get_content_type function."""

    def test_get_content_type_jpg(self):
        """Should return correct content type for JPEG files."""
        assert unzip_lambda.get_content_type("test.jpg") == "image/jpeg"
        assert unzip_lambda.get_content_type("test.jpeg") == "image/jpeg"

    def test_get_content_type_png(self):
        """Should return correct content type for PNG files."""
        assert unzip_lambda.get_content_type("test.png") == "image/png"

    def test_get_content_type_gif(self):
        """Should return correct content type for GIF files."""
        assert unzip_lambda.get_content_type("test.gif") == "image/gif"

    def test_get_content_type_default(self):
        """Should return default for unknown extensions."""
        assert unzip_lambda.get_content_type("test.txt") == "application/octet-stream"


class TestExtractImagesFromZip:
    """Tests for extract_images_from_zip function."""

    def test_extract_images_from_zip_success(self, aws_credentials, monkeypatch):
        """Should extract image files from ZIP and upload to S3."""
        import boto3
        from moto import mock_aws

        with mock_aws():
            # Create S3 client inside mock context
            s3_client = boto3.client("s3", region_name="eu-west-2")

            # Create test ZIP file with images
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("image1.jpg", b"fake image data 1")
                zf.writestr("image2.png", b"fake image data 2")
                zf.writestr("readme.txt", b"not an image")

            zip_content = zip_buffer.getvalue()

            # Create source bucket and upload ZIP
            s3_client.create_bucket(
                Bucket="aws-sudoblark-development-demos-landing",
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            s3_client.put_object(
                Bucket="aws-sudoblark-development-demos-landing", Key="test.zip", Body=zip_content
            )

            # Create destination bucket
            s3_client.create_bucket(
                Bucket="aws-sudoblark-development-demos-raw",
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )

            # Extract images
            result = unzip_lambda.extract_images_from_zip(
                "aws-sudoblark-development-demos-landing", "test.zip", "raw"
            )

            # Verify results
            assert len(result) == 2
            assert "image1.jpg" in result
            assert "image2.png" in result

            # Verify files uploaded to S3
            objects = s3_client.list_objects_v2(Bucket="aws-sudoblark-development-demos-raw")
            assert objects["KeyCount"] == 2

    def test_extract_images_from_zip_no_images(self, aws_credentials, monkeypatch):
        """Should return empty list when no images in ZIP."""
        import boto3
        from moto import mock_aws

        with mock_aws():
            # Create S3 client inside mock context
            s3_client = boto3.client("s3", region_name="eu-west-2")

            # Create ZIP with only text files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("readme.txt", b"text file")
                zf.writestr("config.json", b"{}")

            zip_content = zip_buffer.getvalue()

            s3_client.create_bucket(
                Bucket="aws-sudoblark-development-demos-landing",
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            s3_client.put_object(
                Bucket="aws-sudoblark-development-demos-landing", Key="test.zip", Body=zip_content
            )

            s3_client.create_bucket(
                Bucket="aws-sudoblark-development-demos-raw",
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )

            result = unzip_lambda.extract_images_from_zip(
                "aws-sudoblark-development-demos-landing", "test.zip", "raw"
            )

            assert len(result) == 0

    def test_extract_images_invalid_bucket_format(self):
        """Should raise ValueError for invalid bucket format."""
        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            unzip_lambda.extract_images_from_zip("short", "test.zip", "raw")

    def test_extract_images_empty_inputs(self):
        """Should raise ValueError for empty inputs."""
        with pytest.raises(
            ValueError, match="source_bucket, zip_key, and raw_bucket_name must not be empty"
        ):
            unzip_lambda.extract_images_from_zip("", "test.zip", "raw")

        with pytest.raises(
            ValueError, match="source_bucket, zip_key, and raw_bucket_name must not be empty"
        ):
            unzip_lambda.extract_images_from_zip("test-bucket", "", "raw")

        with pytest.raises(
            ValueError, match="source_bucket, zip_key, and raw_bucket_name must not be empty"
        ):
            unzip_lambda.extract_images_from_zip("test-bucket", "test.zip", "")


class TestHandler:
    """Tests for Lambda handler function."""

    @patch("unzip_lambda_function.extract_images_from_zip")
    def test_handler_success(self, mock_extract, sample_s3_event, lambda_context, monkeypatch):
        """Should process S3 event and extract images."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        mock_extract.return_value = ["image1.jpg", "image2.png"]

        response = unzip_lambda.handler(sample_s3_event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 2  # Count of extracted images, not records
        assert response["failed_count"] == 0

        # Verify extract was called with correct args
        mock_extract.assert_called_once_with("test-bucket", "test-file.zip", "test-raw-bucket")

    @patch("unzip_lambda_function.extract_images_from_zip")
    def test_handler_partial_failure(self, mock_extract, lambda_context, monkeypatch):
        """Should handle partial failures gracefully."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        # Create event with multiple records
        event = {
            "Records": [
                {"s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "file1.zip"}}},
                {"s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "file2.zip"}}},
            ]
        }

        # First succeeds, second fails
        mock_extract.side_effect = [["image1.jpg"], Exception("S3 error")]

        response = unzip_lambda.handler(event, lambda_context)

        assert response["statusCode"] == 207  # Multi-status
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1

    def test_handler_missing_config(self, sample_s3_event, lambda_context, monkeypatch):
        """Should raise error when configuration is invalid."""
        monkeypatch.delenv("RAW_BUCKET", raising=False)

        with pytest.raises(ValueError):
            unzip_lambda.handler(sample_s3_event, lambda_context)
