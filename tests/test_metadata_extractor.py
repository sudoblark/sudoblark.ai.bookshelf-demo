"""Tests for metadata-extractor Lambda function."""

import importlib.util
import io
import os

# Add lambda-packages to path for imports
import sys
from unittest.mock import patch

import pytest
from PIL import Image

# Dynamically import lambda_function from metadata-extractor directory
spec = importlib.util.spec_from_file_location(
    "metadata_lambda_function",
    os.path.join(
        os.path.dirname(__file__), "../lambda-packages/metadata-extractor/lambda_function.py"
    ),
)
metadata_lambda = importlib.util.module_from_spec(spec)
sys.modules["metadata_lambda_function"] = metadata_lambda
spec.loader.exec_module(metadata_lambda)


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_success(self, monkeypatch):
        """Should return config when all required env vars are set."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = metadata_lambda.get_config()

        assert config["processed_bucket"] == "test-processed-bucket"
        assert config["bedrock_model_id"] == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config["log_level"] == "INFO"

    def test_get_config_missing_processed_bucket(self, monkeypatch):
        """Should raise ValueError when PROCESSED_BUCKET is missing."""
        monkeypatch.delenv("PROCESSED_BUCKET", raising=False)
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        with pytest.raises(ValueError, match="PROCESSED_BUCKET environment variable is required"):
            metadata_lambda.get_config()

    def test_get_config_default_bedrock_model(self, monkeypatch):
        """Should use default BEDROCK_MODEL_ID when not specified."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-bucket")
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        config = metadata_lambda.get_config()

        assert config["bedrock_model_id"] == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_get_config_invalid_log_level(self, monkeypatch):
        """Should raise ValueError for invalid LOG_LEVEL."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            metadata_lambda.get_config()


class TestResizeImageToJpeg:
    """Tests for resize_image_to_jpeg function."""

    def test_resize_large_image(self):
        """Should resize large image to max dimension."""
        img = Image.new("RGB", (2000, 1500), color="blue")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        resized = metadata_lambda.resize_image_to_jpeg(img_bytes, max_dim=1024)

        # Verify it's still valid JPEG
        resized_img = Image.open(io.BytesIO(resized))
        assert resized_img.format == "JPEG"
        assert max(resized_img.size) == 1024

    def test_resize_small_image(self):
        """Should not upscale small images."""
        img = Image.new("RGB", (500, 400), color="green")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        resized = metadata_lambda.resize_image_to_jpeg(img_bytes, max_dim=1024)

        resized_img = Image.open(io.BytesIO(resized))
        assert resized_img.size == (500, 400)


class TestEnsureMetadataDefaults:
    """Tests for ensure_metadata_defaults function."""

    def test_add_missing_fields(self):
        """Should add missing required fields."""
        metadata = {"title": "Test Book"}

        result = metadata_lambda.ensure_metadata_defaults(metadata, "book.jpg")

        assert "id" in result
        assert result["filename"] == "book.jpg"
        assert "processed_at" in result
        assert result["title"] == "Test Book"

    def test_preserve_existing_fields(self):
        """Should not overwrite existing fields."""
        metadata = {
            "id": "existing-id",
            "title": "Test",
            "filename": "original.jpg",
            "processed_at": "2026-01-01T00:00:00Z",
        }

        result = metadata_lambda.ensure_metadata_defaults(metadata, "new.jpg")

        assert result["id"] == "existing-id"
        assert result["filename"] == "original.jpg"
        assert result["processed_at"] == "2026-01-01T00:00:00Z"


class TestParseBedRockResponse:
    """Tests for parse_bedrock_response function."""

    def test_parse_valid_json(self):
        """Should parse valid JSON metadata."""
        response_text = """
        {
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "isbn": "978-0-7432-7356-5",
            "publisher": "Scribner",
            "year": "1925"
        }
        """

        result = metadata_lambda.parse_bedrock_response(response_text)

        assert result["title"] == "The Great Gatsby"
        assert result["author"] == "F. Scott Fitzgerald"
        assert result["isbn"] == "978-0-7432-7356-5"

    def test_parse_json_with_markdown_wrapper(self):
        """Should extract JSON from markdown code blocks."""
        response_text = """
        Here's the metadata:
        ```json
        {
            "title": "1984",
            "author": "George Orwell"
        }
        ```
        """

        result = metadata_lambda.parse_bedrock_response(response_text)

        assert result["title"] == "1984"
        assert result["author"] == "George Orwell"

    def test_parse_invalid_json(self):
        """Should return empty metadata fields for invalid JSON."""
        response_text = "This is not JSON"

        result = metadata_lambda.parse_bedrock_response(response_text)

        # Should return default empty values
        assert result["title"] == ""
        assert result["author"] == ""
        assert result["publisher"] == ""


class TestWriteMetadataToParquet:
    """Tests for write_metadata_to_parquet function."""

    def test_write_metadata_success(self, s3_client):
        """Should convert metadata to Parquet and upload to S3."""
        s3_client.create_bucket(
            Bucket="test-processed", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        metadata = {
            "id": "test-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "123456789",
        }

        parquet_key = metadata_lambda.write_metadata_to_parquet(metadata, "test-processed")

        assert parquet_key.endswith(".parquet")
        assert "metadata_" in parquet_key

        # Verify file was uploaded
        objects = s3_client.list_objects_v2(Bucket="test-processed")
        assert objects["KeyCount"] == 1

    def test_write_metadata_empty_metadata(self):
        """Should raise ValueError for empty metadata."""
        with pytest.raises(ValueError, match="metadata and processed_bucket must not be empty"):
            metadata_lambda.write_metadata_to_parquet({}, "test-bucket")

    def test_write_metadata_empty_bucket(self):
        """Should raise ValueError for empty bucket."""
        metadata = {"id": "test", "title": "Test"}
        with pytest.raises(ValueError, match="metadata and processed_bucket must not be empty"):
            metadata_lambda.write_metadata_to_parquet(metadata, "")


class TestProcessImageToParquet:
    """Tests for process_image_to_parquet function."""

    @patch("metadata_lambda_function.extract_metadata_with_bedrock")
    def test_process_image_success(self, mock_bedrock, s3_client, monkeypatch):
        """Should process image and write Parquet file."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        # Create test image
        img = Image.new("RGB", (100, 100), color="red")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        # Upload to S3
        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(
            Bucket="aws-sudoblark-development-demos-raw", Key="book.jpg", Body=img_bytes
        )

        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-processed",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        # Mock Bedrock response
        mock_bedrock.return_value = {
            "id": "test-id-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "123-456-789",
            "filename": "book.jpg",
            "processed_at": "2026-03-09T10:00:00Z",
        }

        # Process image
        config = metadata_lambda.get_config()
        parquet_key = metadata_lambda.process_image_to_parquet(
            "aws-sudoblark-development-demos-raw", "book.jpg", config
        )

        # Verify parquet key is returned
        assert parquet_key.endswith(".parquet")

        # Verify Bedrock was called with correct parameters
        mock_bedrock.assert_called_once()

        # Verify Parquet file was created in S3
        objects = s3_client.list_objects_v2(Bucket="aws-sudoblark-development-demos-processed")
        assert objects["KeyCount"] >= 1

    @patch("metadata_lambda_function.extract_metadata_with_bedrock")
    def test_process_image_bedrock_failure(self, mock_bedrock, s3_client, monkeypatch):
        """Should handle Bedrock API failures gracefully."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        # Create test image
        img = Image.new("RGB", (100, 100), color="red")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(
            Bucket="aws-sudoblark-development-demos-raw", Key="book.jpg", Body=img_bytes
        )

        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-processed",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        # Mock Bedrock to raise error
        mock_bedrock.side_effect = Exception("Bedrock API error")

        config = metadata_lambda.get_config()

        with pytest.raises(Exception, match="Bedrock API error"):
            metadata_lambda.process_image_to_parquet(
                "aws-sudoblark-development-demos-raw", "book.jpg", config
            )

    def test_process_image_invalid_bucket_format(self, monkeypatch):
        """Should raise ValueError for invalid bucket name format."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        config = metadata_lambda.get_config()

        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            metadata_lambda.process_image_to_parquet("short-bucket", "book.jpg", config)

    def test_process_image_empty_inputs(self, monkeypatch):
        """Should raise ValueError for empty inputs."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed")
        config = metadata_lambda.get_config()

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            metadata_lambda.process_image_to_parquet("", "book.jpg", config)

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            metadata_lambda.process_image_to_parquet("test-bucket", "", config)


class TestHandler:
    """Tests for Lambda handler function."""

    @patch("metadata_lambda_function.process_image_to_parquet")
    def test_handler_success(self, mock_process, sample_s3_event, lambda_context, monkeypatch):
        """Should process S3 event and extract metadata."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        mock_process.return_value = {"title": "Test Book", "author": "Test Author"}

        response = metadata_lambda.handler(sample_s3_event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 1
        assert response["failed_count"] == 0

        # Verify process was called with correct bucket and key
        call_args = mock_process.call_args[0]
        assert call_args[0] == "test-bucket"
        assert call_args[1] == "test-file.zip"

    @patch("metadata_lambda_function.process_image_to_parquet")
    def test_handler_multiple_records(self, mock_process, lambda_context, monkeypatch):
        """Should process multiple S3 records."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        event = {
            "Records": [
                {"s3": {"bucket": {"name": "bucket1"}, "object": {"key": "image1.jpg"}}},
                {"s3": {"bucket": {"name": "bucket2"}, "object": {"key": "image2.jpg"}}},
            ]
        }

        mock_process.return_value = {"title": "Test"}

        response = metadata_lambda.handler(event, lambda_context)

        assert response["processed_count"] == 2
        assert response["failed_count"] == 0
        assert mock_process.call_count == 2

    @patch("metadata_lambda_function.process_image_to_parquet")
    def test_handler_partial_failure(self, mock_process, lambda_context, monkeypatch):
        """Should handle partial failures and return multi-status."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        event = {
            "Records": [
                {"s3": {"bucket": {"name": "bucket1"}, "object": {"key": "image1.jpg"}}},
                {"s3": {"bucket": {"name": "bucket2"}, "object": {"key": "image2.jpg"}}},
            ]
        }

        # First succeeds, second fails
        mock_process.side_effect = [{"title": "Test"}, Exception("Processing error")]

        response = metadata_lambda.handler(event, lambda_context)

        assert response["statusCode"] == 207  # Multi-status
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1
