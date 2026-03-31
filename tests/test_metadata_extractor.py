"""Tests for metadata-extractor Lambda function."""

import importlib.util
import io
import os

# Add metadata-extractor to sys.path so local imports resolve
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

_LAMBDA_DIR = os.path.join(
    os.path.dirname(__file__), "../application/backend/data-pipeline/metadata-extractor"
)
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

DATA_LAKE_PREFIX = "aws-sudoblark-development-bookshelf-demo"
RAW_BUCKET = f"{DATA_LAKE_PREFIX}-raw"
PROCESSED_BUCKET = f"{DATA_LAKE_PREFIX}-processed"


class TestConfig:
    """Tests for the Config class."""

    def test_from_env_success(self, monkeypatch):
        """Should return a Config when all required env vars are set."""
        monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        monkeypatch.setenv("LOG_LEVEL", "INFO")

        config = metadata_lambda.Config.from_env()

        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.log_level == "INFO"

    def test_from_env_default_bedrock_model(self, monkeypatch):
        """Should use default BEDROCK_MODEL_ID when not specified."""
        monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

        config = metadata_lambda.Config.from_env()

        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_from_env_invalid_log_level(self, monkeypatch):
        """Should raise ValueError for an invalid LOG_LEVEL."""
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


class TestBookshelfAgent:
    """Tests for BookshelfAgent."""

    def _make_agent(self, mock_client=None):
        if mock_client is None:
            mock_client = MagicMock()
        return metadata_lambda.BookshelfAgent("test-model", mock_client)

    def test_run_empty_image_bytes(self):
        """Should raise ValueError for empty image bytes."""
        agent = self._make_agent()

        with pytest.raises(ValueError, match="image_bytes must not be empty"):
            agent.run(b"")

    def test_run_returns_book_metadata(self):
        """Should return a BookMetadata instance with extracted fields."""
        agent = self._make_agent()

        img_buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(img_buffer, format="JPEG")

        with agent._agent.override(
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
            result = agent.run(img_buffer.getvalue())

        assert result.title == "The Great Gatsby"
        assert result.author == "F. Scott Fitzgerald"
        assert result.isbn == "9780743273565"

    def test_run_model_failure_propagates(self):
        """Should propagate exceptions raised by the underlying model."""
        agent = self._make_agent()

        img_buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(img_buffer, format="JPEG")

        def failing_model(messages: list[ModelMessage], info: AgentInfo) -> None:
            raise UnexpectedModelBehavior("Model unavailable")

        with agent._agent.override(model=FunctionModel(failing_model)):
            with pytest.raises(Exception):
                agent.run(img_buffer.getvalue())


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


def _make_book_metadata(title: str = "Test Book"):
    """Return a BookMetadata instance for use as BookshelfAgent.run() mock return value."""
    from models import BookMetadata

    return BookMetadata(
        title=title,
        author="Test Author",
        isbn="1234567890",
        publisher="Test Publisher",
        published_year=2024,
        description="Test description",
        confidence=0.9,
    )


class TestBookshelfProcessor:
    """Tests for BookshelfProcessor."""

    def _make_image_bytes(self):
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), color="red").save(buf, format="JPEG")
        return buf.getvalue()

    # --- _apply_defaults ---

    def test_apply_defaults_adds_missing_fields(self):
        """Should add id, filename, and processed_at when absent."""
        processor = metadata_lambda.BookshelfProcessor(MagicMock(), MagicMock())
        metadata = {"title": "Test Book"}

        result = processor._apply_defaults(metadata, "book.jpg")

        assert "id" in result
        assert result["filename"] == "book.jpg"
        assert "processed_at" in result
        assert result["title"] == "Test Book"

    def test_apply_defaults_preserves_existing_fields(self):
        """Should not overwrite fields that already exist."""
        processor = metadata_lambda.BookshelfProcessor(MagicMock(), MagicMock())
        metadata = {
            "id": "existing-id",
            "filename": "original.jpg",
            "processed_at": "2026-01-01T00:00:00Z",
        }

        result = processor._apply_defaults(metadata, "new.jpg")

        assert result["id"] == "existing-id"
        assert result["filename"] == "original.jpg"
        assert result["processed_at"] == "2026-01-01T00:00:00Z"

    # --- process ---

    def test_process_success(self, s3_client, mocker):
        """Should download image, extract metadata, and write a Parquet file."""
        image_bytes = self._make_image_bytes()

        s3_client.create_bucket(
            Bucket="test-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(Bucket="test-raw", Key="book.jpg", Body=image_bytes)
        s3_client.create_bucket(
            Bucket="test-processed",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_book_metadata()
        processor = metadata_lambda.BookshelfProcessor(mock_agent, s3_client)

        parquet_key = processor.process("test-raw", "test-processed", "book.jpg")

        assert parquet_key.endswith(".parquet")
        objects = s3_client.list_objects_v2(Bucket="test-processed")
        assert objects["KeyCount"] >= 1

    def test_process_extractor_failure(self, s3_client, mocker):
        """Should propagate exceptions from the agent."""
        image_bytes = self._make_image_bytes()

        s3_client.create_bucket(
            Bucket="test-raw",
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(Bucket="test-raw", Key="book.jpg", Body=image_bytes)

        mock_agent = MagicMock()
        mock_agent.run.side_effect = Exception("Bedrock API error")
        processor = metadata_lambda.BookshelfProcessor(mock_agent, s3_client)

        with pytest.raises(Exception, match="Bedrock API error"):
            processor.process("test-raw", "test-processed", "book.jpg")

    def test_process_empty_inputs(self):
        """Should raise ValueError for empty source_bucket or image_key."""
        processor = metadata_lambda.BookshelfProcessor(MagicMock(), MagicMock())

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            processor.process("", "test-processed", "book.jpg")

        with pytest.raises(ValueError, match="source_bucket and image_key must not be empty"):
            processor.process("test-raw", "test-processed", "")

    def test_process_s3_client_error(self, s3_client, mocker):
        """Should propagate S3 ClientError when put_object fails."""
        from botocore.exceptions import ClientError

        image_bytes = self._make_image_bytes()

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: image_bytes)}
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )

        mock_agent = MagicMock()
        mock_agent.run.return_value = _make_book_metadata()
        processor = metadata_lambda.BookshelfProcessor(mock_agent, mock_s3)

        with pytest.raises(ClientError):
            processor.process("test-raw", "test-processed", "test.jpg")


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_handler_success(self, lambda_context):
        """Should process an S3 event and return a success response."""
        mock_processor = MagicMock()
        mock_processor.process.return_value = "processed/year=2026/test.parquet"
        metadata_lambda.handler._processor = mock_processor
        metadata_lambda.handler._tracker = MagicMock()

        event = {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "eventName": "ObjectCreated:Put",
                    "s3": {
                        "bucket": {
                            "name": RAW_BUCKET,
                            "arn": f"arn:aws:s3:::{RAW_BUCKET}",
                        },
                        "object": {"key": "uploads/user-1/upload-1/cover.jpg", "size": 1024},
                    },
                }
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert response["processed_count"] == 1
        assert response["failed_count"] == 0
        mock_processor.process.assert_called_once_with(
            RAW_BUCKET, PROCESSED_BUCKET, "uploads/user-1/upload-1/cover.jpg"
        )

    def test_handler_multiple_records(self, lambda_context):
        """Should process multiple S3 records."""
        mock_processor = MagicMock()
        mock_processor.process.return_value = "processed/key.parquet"
        metadata_lambda.handler._processor = mock_processor
        metadata_lambda.handler._tracker = MagicMock()

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": RAW_BUCKET},
                        "object": {"key": "uploads/u/up1/img1.jpg"},
                    }
                },
                {
                    "s3": {
                        "bucket": {"name": RAW_BUCKET},
                        "object": {"key": "uploads/u/up2/img2.jpg"},
                    }
                },
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["processed_count"] == 2
        assert response["failed_count"] == 0
        assert mock_processor.process.call_count == 2

    def test_handler_partial_failure(self, lambda_context):
        """Should handle partial failures and return a multi-status response."""
        mock_processor = MagicMock()
        mock_processor.process.side_effect = [
            "processed/key.parquet",
            Exception("Processing error"),
        ]
        metadata_lambda.handler._processor = mock_processor
        metadata_lambda.handler._tracker = MagicMock()

        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": RAW_BUCKET},
                        "object": {"key": "uploads/u/up1/img1.jpg"},
                    }
                },
                {
                    "s3": {
                        "bucket": {"name": RAW_BUCKET},
                        "object": {"key": "uploads/u/up2/img2.jpg"},
                    }
                },
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["statusCode"] == 207
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1

    def test_handler_path_traversal_attack(self, lambda_context):
        """Should reject path traversal attempts and report the failure."""
        event = {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": RAW_BUCKET},
                        "object": {"key": "../../../etc/passwd"},
                    },
                }
            ]
        }

        response = metadata_lambda.handler(event, lambda_context)

        assert response["failed_count"] == 1
        assert "path traversal" in str(response["failed_files"][0]["error"]).lower()

    def test_handler_general_exception(self, lambda_context):
        """Should re-raise exceptions caused by a malformed event structure."""
        event = {"Records": [{}]}

        with pytest.raises(Exception):
            metadata_lambda.handler(event, lambda_context)
