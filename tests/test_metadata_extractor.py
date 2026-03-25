"""Tests for metadata-extractor Lambda function."""

import importlib.util
import io
import os

# Add lambda-packages/metadata-extractor to sys.path so local imports resolve
import sys
from unittest.mock import MagicMock

import pydantic_ai.models as pydantic_ai_models
import pytest
from PIL import Image
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

pydantic_ai_models.ALLOW_MODEL_REQUESTS = False

_LAMBDA_DIR = os.path.join(os.path.dirname(__file__), "../lambda-packages/metadata-extractor")
if _LAMBDA_DIR not in sys.path:
    sys.path.insert(0, _LAMBDA_DIR)

# Dynamically import lambda_function from metadata-extractor directory
spec = importlib.util.spec_from_file_location(
    "metadata_lambda_function",
    os.path.join(_LAMBDA_DIR, "lambda_function.py"),
)
metadata_lambda = importlib.util.module_from_spec(spec)
sys.modules["metadata_lambda_function"] = metadata_lambda
spec.loader.exec_module(metadata_lambda)


class TestConfig:
    """Tests for the Config class."""

    def test_from_env_success(self, monkeypatch):
        """Should return a Config when all required env vars are set."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = metadata_lambda.Config.from_env()

        assert config.processed_bucket == "test-processed-bucket"
        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.log_level == "INFO"

    def test_from_env_missing_processed_bucket(self, monkeypatch):
        """Should raise ValueError when PROCESSED_BUCKET is missing."""
        monkeypatch.delenv("PROCESSED_BUCKET", raising=False)
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        with pytest.raises(ValueError, match="PROCESSED_BUCKET environment variable is required"):
            metadata_lambda.Config.from_env()

    def test_from_env_default_bedrock_model(self, monkeypatch):
        """Should use default BEDROCK_MODEL_ID when not specified."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-bucket")
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        config = metadata_lambda.Config.from_env()

        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_from_env_invalid_log_level(self, monkeypatch):
        """Should raise ValueError for an invalid LOG_LEVEL."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-bucket")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            metadata_lambda.Config.from_env()


class TestImageProcessor:
    """Tests for ImageProcessor."""

    def test_resize_large_image(self):
        """Should resize a large image to the max dimension."""
        img = Image.new("RGB", (2000, 1500), color="blue")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        resized = metadata_lambda.ImageProcessor.resize_to_jpeg(img_bytes, max_dim=1024)

        resized_img = Image.open(io.BytesIO(resized))
        assert resized_img.format == "JPEG"
        assert max(resized_img.size) == 1024

    def test_resize_small_image(self):
        """Should not upscale images smaller than max_dim."""
        img = Image.new("RGB", (500, 400), color="green")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        resized = metadata_lambda.ImageProcessor.resize_to_jpeg(img_bytes, max_dim=1024)

        resized_img = Image.open(io.BytesIO(resized))
        assert resized_img.size == (500, 400)

    def test_resize_empty_bytes(self):
        """Should raise ValueError for empty bytes."""
        with pytest.raises(ValueError, match="image_bytes must not be empty"):
            metadata_lambda.ImageProcessor.resize_to_jpeg(b"")

    def test_resize_invalid_image_data(self):
        """Should raise an exception for invalid image data."""
        with pytest.raises(Exception):
            metadata_lambda.ImageProcessor.resize_to_jpeg(b"not an image")


class TestBedrockMetadataExtractor:
    """Tests for BedrockMetadataExtractor."""

    def _make_extractor(self, mock_client=None):
        if mock_client is None:
            mock_client = MagicMock()
        return metadata_lambda.BedrockMetadataExtractor("test-model", mock_client)

    # --- _apply_defaults ---

    def test_apply_defaults_adds_missing_fields(self):
        """Should add id, filename, and processed_at when absent."""
        extractor = self._make_extractor()
        metadata = {"title": "Test Book"}

        result = extractor._apply_defaults(metadata, "book.jpg")

        assert "id" in result
        assert result["filename"] == "book.jpg"
        assert "processed_at" in result
        assert result["title"] == "Test Book"

    def test_apply_defaults_preserves_existing_fields(self):
        """Should not overwrite fields that already exist."""
        extractor = self._make_extractor()
        metadata = {
            "id": "existing-id",
            "filename": "original.jpg",
            "processed_at": "2026-01-01T00:00:00Z",
        }

        result = extractor._apply_defaults(metadata, "new.jpg")

        assert result["id"] == "existing-id"
        assert result["filename"] == "original.jpg"
        assert result["processed_at"] == "2026-01-01T00:00:00Z"

    # --- extract ---

    def test_extract_empty_image_bytes(self):
        """Should raise ValueError for empty image bytes."""
        extractor = self._make_extractor()

        with pytest.raises(ValueError, match="image_bytes must not be empty"):
            extractor.extract(b"", "test.jpg")

    def test_extract_returns_metadata_with_defaults(self):
        """Should return validated metadata with id, filename, and processed_at populated."""
        extractor = self._make_extractor()

        img_buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(img_buffer, format="JPEG")

        with extractor._agent.override(
            model=TestModel(
                custom_output_args={
                    "title": "The Great Gatsby",
                    "author": "F. Scott Fitzgerald",
                    "isbn": "9780743273565",
                    "publisher": "Scribner",
                    "published_year": 1925,
                    "description": "A classic novel.",
                    "confidence": 0.95,
                }
            )
        ):
            result = extractor.extract(img_buffer.getvalue(), "test.jpg")

        assert result["title"] == "The Great Gatsby"
        assert result["author"] == "F. Scott Fitzgerald"
        assert result["filename"] == "test.jpg"
        assert "id" in result
        assert "processed_at" in result

    def test_extract_model_failure_propagates(self):
        """Should propagate exceptions raised by the underlying model."""
        extractor = self._make_extractor()

        img_buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(img_buffer, format="JPEG")

        def failing_model(messages: list[ModelMessage], info: AgentInfo) -> None:
            raise UnexpectedModelBehavior("Model unavailable")

        with extractor._agent.override(model=FunctionModel(failing_model)):
            with pytest.raises(Exception):
                extractor.extract(img_buffer.getvalue(), "test.jpg")


class TestParquetWriter:
    """Tests for ParquetWriter."""

    def test_write_success(self, s3_client):
        """Should convert metadata to Parquet and upload to S3."""
        s3_client.create_bucket(
            Bucket="test-processed", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        writer = metadata_lambda.ParquetWriter(s3_client)
        metadata = {
            "id": "test-123",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "123456789",
        }

        parquet_key = writer.write(metadata, "test-processed")

        assert parquet_key.endswith(".parquet")
        assert "metadata_" in parquet_key

        objects = s3_client.list_objects_v2(Bucket="test-processed")
        assert objects["KeyCount"] == 1

    def test_write_empty_metadata_raises(self):
        """Should raise ValueError for empty metadata."""
        writer = metadata_lambda.ParquetWriter(MagicMock())

        with pytest.raises(ValueError, match="metadata and processed_bucket must not be empty"):
            writer.write({}, "test-bucket")

    def test_write_empty_bucket_raises(self):
        """Should raise ValueError for empty bucket."""
        writer = metadata_lambda.ParquetWriter(MagicMock())

        with pytest.raises(ValueError, match="metadata and processed_bucket must not be empty"):
            writer.write({"id": "test", "title": "Test"}, "")


class TestBookshelfProcessor:
    """Tests for BookshelfProcessor."""

    def _make_config(self, monkeypatch, processed_bucket="processed", model="test-model"):
        monkeypatch.setenv("PROCESSED_BUCKET", processed_bucket)
        monkeypatch.setenv("BEDROCK_MODEL_ID", model)
        return metadata_lambda.Config.from_env()

    def _make_image_bytes(self):
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(buf, format="JPEG")
        return buf.getvalue()

    def _make_extract_return_value(self, title: str = "Test Book") -> dict:
        return {
            "id": "test-id-123",
            "title": title,
            "author": "Test Author",
            "isbn": "1234567890",
            "publisher": "Test Publisher",
            "published_year": 2024,
            "description": "Test description",
            "confidence": 0.9,
            "filename": "book.jpg",
            "processed_at": "2026-01-01T00:00:00Z",
        }

    def test_process_success(self, s3_client, mocker, monkeypatch):
        """Should download image, extract metadata, and write a Parquet file."""
        config = self._make_config(monkeypatch)
        image_bytes = self._make_image_bytes()

        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(
            Bucket="aws-sudoblark-development-demos-raw", Key="book.jpg", Body=image_bytes
        )
        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-processed",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        mocker.patch.object(
            metadata_lambda.BedrockMetadataExtractor,
            "extract",
            return_value=self._make_extract_return_value(),
        )
        processor = metadata_lambda.BookshelfProcessor(config, s3_client, MagicMock())

        parquet_key = processor.process("aws-sudoblark-development-demos-raw", "book.jpg")

        assert parquet_key.endswith(".parquet")
        objects = s3_client.list_objects_v2(Bucket="aws-sudoblark-development-demos-processed")
        assert objects["KeyCount"] >= 1

    def test_process_extractor_failure(self, s3_client, monkeypatch, mocker):
        """Should propagate exceptions from the metadata extractor."""
        config = self._make_config(monkeypatch)
        image_bytes = self._make_image_bytes()

        s3_client.create_bucket(
            Bucket="aws-sudoblark-development-demos-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(
            Bucket="aws-sudoblark-development-demos-raw", Key="book.jpg", Body=image_bytes
        )

        mocker.patch.object(
            metadata_lambda.BedrockMetadataExtractor,
            "extract",
            side_effect=Exception("Bedrock API error"),
        )
        processor = metadata_lambda.BookshelfProcessor(config, s3_client, MagicMock())

        with pytest.raises(Exception, match="Bedrock API error"):
            processor.process("aws-sudoblark-development-demos-raw", "book.jpg")

    def test_process_invalid_bucket_format(self, monkeypatch):
        """Should raise ValueError for an invalid source bucket name format."""
        config = self._make_config(monkeypatch)
        processor = metadata_lambda.BookshelfProcessor(config, MagicMock(), MagicMock())

        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            processor.process("short-bucket", "book.jpg")

    def test_process_empty_inputs(self, monkeypatch):
        """Should raise ValueError for empty source_bucket or image_key."""
        config = self._make_config(monkeypatch)
        processor = metadata_lambda.BookshelfProcessor(config, MagicMock(), MagicMock())

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            processor.process("", "book.jpg")

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            processor.process("test-bucket", "")

    def test_process_s3_client_error(self, s3_client, mocker, monkeypatch):
        """Should propagate S3 ClientError when put_object fails."""
        from botocore.exceptions import ClientError

        config = self._make_config(monkeypatch, processed_bucket="processed")
        image_bytes = self._make_image_bytes()

        source_bucket = "test-account-project-app-source"
        s3_client.create_bucket(
            Bucket=source_bucket, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )
        s3_client.put_object(Bucket=source_bucket, Key="test.jpg", Body=image_bytes)

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: image_bytes)}
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )

        mocker.patch.object(
            metadata_lambda.BedrockMetadataExtractor,
            "extract",
            return_value=self._make_extract_return_value(),
        )
        processor = metadata_lambda.BookshelfProcessor(config, mock_s3, MagicMock())

        with pytest.raises(ClientError):
            processor.process(source_bucket, "test.jpg")


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_handler_success(self, sample_s3_event, lambda_context, monkeypatch):
        """Should process an S3 event and return a success response."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        mock_processor = MagicMock()
        mock_processor.process.return_value = "processed/year=2026/test.parquet"
        monkeypatch.setattr(metadata_lambda.handler, "_processor", mock_processor)

        response = metadata_lambda.handler(sample_s3_event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 1
        assert response["failed_count"] == 0
        mock_processor.process.assert_called_once_with("test-bucket", "test-file.zip")

    def test_handler_multiple_records(self, lambda_context, monkeypatch):
        """Should process multiple S3 records."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        mock_processor = MagicMock()
        mock_processor.process.return_value = "processed/key.parquet"
        monkeypatch.setattr(metadata_lambda.handler, "_processor", mock_processor)

        event = {
            "Records": [
                {"s3": {"bucket": {"name": "bucket1"}, "object": {"key": "image1.jpg"}}},
                {"s3": {"bucket": {"name": "bucket2"}, "object": {"key": "image2.jpg"}}},
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["processed_count"] == 2
        assert response["failed_count"] == 0
        assert mock_processor.process.call_count == 2

    def test_handler_partial_failure(self, lambda_context, monkeypatch):
        """Should handle partial failures and return a multi-status response."""
        monkeypatch.setenv("PROCESSED_BUCKET", "processed-bucket")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")

        mock_processor = MagicMock()
        mock_processor.process.side_effect = [
            "processed/key.parquet",
            Exception("Processing error"),
        ]
        monkeypatch.setattr(metadata_lambda.handler, "_processor", mock_processor)

        event = {
            "Records": [
                {"s3": {"bucket": {"name": "bucket1"}, "object": {"key": "image1.jpg"}}},
                {"s3": {"bucket": {"name": "bucket2"}, "object": {"key": "image2.jpg"}}},
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["statusCode"] == 207
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1

    def test_handler_path_traversal_attack(self, lambda_context, monkeypatch):
        """Should reject path traversal attempts and report the failure."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-processed")

        event = {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "../../../etc/passwd"},
                    },
                }
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["failed_count"] == 1
        assert "path traversal" in str(response["failed_files"][0]["error"]).lower()

    def test_handler_general_exception(self, lambda_context, monkeypatch):
        """Should re-raise exceptions caused by a malformed event structure."""
        monkeypatch.setenv("PROCESSED_BUCKET", "test-processed")

        event = {"Records": [{}]}

        with pytest.raises(Exception):
            metadata_lambda.handler(event, lambda_context)
