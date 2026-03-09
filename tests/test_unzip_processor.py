"""Tests for unzip-processor Lambda function."""

import io
import os

# Add lambda-packages to path for imports
import sys
import zipfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../lambda-packages/unzip-processor"))

import lambda_function  # noqa: E402


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_success(self, monkeypatch):
        """Should return config when RAW_BUCKET is set."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = lambda_function.get_config()

        assert config["raw_bucket"] == "test-raw-bucket"
        assert config["log_level"] == "INFO"

    def test_get_config_missing_raw_bucket(self, monkeypatch):
        """Should raise ValueError when RAW_BUCKET is missing."""
        monkeypatch.delenv("RAW_BUCKET", raising=False)

        with pytest.raises(ValueError, match="RAW_BUCKET environment variable is required"):
            lambda_function.get_config()

    def test_get_config_default_log_level(self, monkeypatch):
        """Should use default log level when not specified."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        config = lambda_function.get_config()

        assert config["log_level"] == "INFO"


class TestExtractImagesFromZip:
    """Tests for extract_images_from_zip function."""

    def test_extract_images_from_zip_success(self, s3_client):
        """Should extract image files from ZIP and upload to S3."""
        # Create test ZIP file with images
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("image1.jpg", b"fake image data 1")
            zf.writestr("image2.png", b"fake image data 2")
            zf.writestr("readme.txt", b"not an image")

        zip_content = zip_buffer.getvalue()

        # Create source bucket and upload ZIP
        s3_client.create_bucket(
            Bucket="source-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        s3_client.put_object(Bucket="source-bucket", Key="test.zip", Body=zip_content)

        # Create destination bucket
        s3_client.create_bucket(
            Bucket="dest-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        # Extract images
        result = lambda_function.extract_images_from_zip("source-bucket", "test.zip", "dest-bucket")

        # Verify results
        assert len(result) == 2
        assert "image1.jpg" in result
        assert "image2.png" in result

        # Verify files uploaded to S3
        objects = s3_client.list_objects_v2(Bucket="dest-bucket")
        assert objects["KeyCount"] == 2

    def test_extract_images_from_zip_no_images(self, s3_client):
        """Should return empty list when no images in ZIP."""
        # Create ZIP with only text files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("readme.txt", b"text file")
            zf.writestr("config.json", b"{}")

        zip_content = zip_buffer.getvalue()

        s3_client.create_bucket(
            Bucket="source-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        s3_client.put_object(Bucket="source-bucket", Key="test.zip", Body=zip_content)

        s3_client.create_bucket(
            Bucket="dest-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        result = lambda_function.extract_images_from_zip("source-bucket", "test.zip", "dest-bucket")

        assert len(result) == 0


class TestHandler:
    """Tests for Lambda handler function."""

    @patch("lambda_function.extract_images_from_zip")
    def test_handler_success(self, mock_extract, sample_s3_event, lambda_context, monkeypatch):
        """Should process S3 event and extract images."""
        monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        mock_extract.return_value = ["image1.jpg", "image2.png"]

        response = lambda_function.handler(sample_s3_event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 1
        assert response["failed_count"] == 0

        # Verify extract was called with correct args
        mock_extract.assert_called_once_with("test-bucket", "test-file.zip", "test-raw-bucket")

    @patch("lambda_function.extract_images_from_zip")
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

        response = lambda_function.handler(event, lambda_context)

        assert response["statusCode"] == 207  # Multi-status
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1

    def test_handler_missing_config(self, sample_s3_event, lambda_context, monkeypatch):
        """Should raise error when configuration is invalid."""
        monkeypatch.delenv("RAW_BUCKET", raising=False)

        with pytest.raises(ValueError):
            lambda_function.handler(sample_s3_event, lambda_context)
