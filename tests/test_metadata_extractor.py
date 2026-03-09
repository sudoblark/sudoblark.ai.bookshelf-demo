"""Tests for metadata-extractor Lambda function."""

import io
import os

# Add lambda-packages to path for imports
import sys
from unittest.mock import patch

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../lambda-packages/metadata-extractor"))

import lambda_function  # noqa: E402


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_success(self, monkeypatch):
        """Should return config when all required env vars are set."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = lambda_function.get_config()

        assert config["processed_bucket"] == "test-processed-bucket"
        assert config["bedrock_model_id"] == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config["log_level"] == "INFO"

    def test_get_config_missing_processed_bucket(self, monkeypatch):
        """Should raise ValueError when PROCESSED_BUCKET is missing."""
        monkeypatch.delenv("PROCESSED_BUCKET", raising=False)
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        with pytest.raises(ValueError, match="PROCESSED_BUCKET environment variable is required"):
            lambda_function.get_config()

    def test_get_config_missing_bedrock_model(self, monkeypatch):
        """Should raise ValueError when BEDROCK_MODEL_ID is missing."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-bucket")
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        with pytest.raises(ValueError, match="BEDROCK_MODEL_ID environment variable is required"):
            lambda_function.get_config()


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

        result = lambda_function.parse_bedrock_response(response_text)

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

        result = lambda_function.parse_bedrock_response(response_text)

        assert result["title"] == "1984"
        assert result["author"] == "George Orwell"

    def test_parse_invalid_json(self):
        """Should return error metadata for invalid JSON."""
        response_text = "This is not JSON"

        result = lambda_function.parse_bedrock_response(response_text)

        assert result["title"] == "Error: Could not parse metadata"
        assert "parse_error" in result


class TestProcessImageToParquet:
    """Tests for process_image_to_parquet function."""

    @patch("lambda_function.extract_metadata_with_bedrock")
    def test_process_image_success(self, mock_bedrock, s3_client, monkeypatch):
        """Should process image and write Parquet file."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        # Create test image
        img = Image.new("RGB", (100, 100), color="red")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        # Upload to S3
        s3_client.create_bucket(
            Bucket="source-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        s3_client.put_object(Bucket="source-bucket", Key="book.jpg", Body=img_bytes)

        s3_client.create_bucket(
            Bucket="processed-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        # Mock Bedrock response
        mock_bedrock.return_value = {
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "123-456-789",
        }

        # Process image
        config = lambda_function.get_config()
        result = lambda_function.process_image_to_parquet("source-bucket", "book.jpg", config)

        assert result["title"] == "Test Book"
        assert result["author"] == "Test Author"

        # Verify Parquet file was created in S3
        objects = s3_client.list_objects_v2(Bucket="processed-bucket")
        assert objects["KeyCount"] >= 1

    @patch("lambda_function.extract_metadata_with_bedrock")
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
            Bucket="source-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        s3_client.put_object(Bucket="source-bucket", Key="book.jpg", Body=img_bytes)

        s3_client.create_bucket(
            Bucket="processed-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        # Mock Bedrock to raise error
        mock_bedrock.side_effect = Exception("Bedrock API error")

        config = lambda_function.get_config()

        with pytest.raises(Exception, match="Bedrock API error"):
            lambda_function.process_image_to_parquet("source-bucket", "book.jpg", config)


class TestHandler:
    """Tests for Lambda handler function."""

    @patch("lambda_function.process_image_to_parquet")
    def test_handler_success(self, mock_process, sample_s3_event, lambda_context, monkeypatch):
        """Should process S3 event and extract metadata."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        mock_process.return_value = {"title": "Test Book", "author": "Test Author"}

        response = lambda_function.handler(sample_s3_event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 1
        assert response["failed_count"] == 0

        # Verify process was called with correct bucket and key
        call_args = mock_process.call_args[0]
        assert call_args[0] == "test-bucket"
        assert call_args[1] == "test-file.zip"

    @patch("lambda_function.process_image_to_parquet")
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

        response = lambda_function.handler(event, lambda_context)

        assert response["processed_count"] == 2
        assert response["failed_count"] == 0
        assert mock_process.call_count == 2

    @patch("lambda_function.process_image_to_parquet")
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

        response = lambda_function.handler(event, lambda_context)

        assert response["statusCode"] == 207  # Multi-status
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1
