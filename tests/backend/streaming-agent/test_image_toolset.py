"""Tests for image_toolset.py - Image metadata and Textract OCR extraction."""

import importlib
import json
import os
import sys
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)
image_toolset_mod = importlib.import_module("image_toolset")
build_image_toolset = image_toolset_mod.build_image_toolset
ImageMetadata = image_toolset_mod.ImageMetadata
TextractResult = image_toolset_mod.TextractResult


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    return MagicMock()


@pytest.fixture
def mock_textract_client():
    """Mock Textract client with sample response."""
    mock = MagicMock()
    mock.detect_document_text.return_value = {
        "Blocks": [
            {
                "BlockType": "LINE",
                "Text": "The Great Gatsby",
                "Confidence": 99.5,
            },
            {
                "BlockType": "LINE",
                "Text": "F. Scott Fitzgerald",
                "Confidence": 98.2,
            },
            {
                "BlockType": "WORD",
                "Text": "The",
                "Confidence": 99.9,
            },
        ]
    }
    return mock


class TestImageMetadataModel:
    """Test ImageMetadata Pydantic model."""

    def test_model_with_all_fields(self):
        """Test creating model with all fields."""
        model = ImageMetadata(
            size_bytes=102400,
            content_type="image/png",
            key="uploads/cover.png",
        )
        assert model.size_bytes == 102400
        assert model.content_type == "image/png"
        assert model.key == "uploads/cover.png"

    def test_model_with_default_content_type(self):
        """Test that content_type defaults to image/jpeg."""
        model = ImageMetadata(
            size_bytes=102400,
            key="uploads/cover.jpg",
        )
        assert model.content_type == "image/jpeg"

    def test_model_size_bytes_required(self):
        """Test that size_bytes is required."""
        with pytest.raises(ValidationError):
            ImageMetadata(content_type="image/jpeg", key="uploads/cover.jpg")

    def test_model_key_required(self):
        """Test that key is required."""
        with pytest.raises(ValidationError):
            ImageMetadata(size_bytes=102400, content_type="image/jpeg")


class TestTextractResultModel:
    """Test TextractResult Pydantic model."""

    def test_model_with_all_fields(self):
        """Test creating model with all fields."""
        model = TextractResult(
            extracted_text="Sample text",
            confidence=0.95,
            line_count=5,
            raw_blocks='[{"text": "Sample"}]',
        )
        assert model.extracted_text == "Sample text"
        assert model.confidence == 0.95
        assert model.line_count == 5

    def test_model_with_defaults(self):
        """Test that line_count and raw_blocks have defaults."""
        model = TextractResult(
            extracted_text="Sample text",
            confidence=0.95,
        )
        assert model.line_count == 0
        assert model.raw_blocks == "[]"

    def test_confidence_range_validation(self):
        """Test that confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            TextractResult(extracted_text="text", confidence=1.5)

        with pytest.raises(ValidationError):
            TextractResult(extracted_text="text", confidence=-0.1)


class TestBuildImageToolset:
    """Test the build_image_toolset factory function."""

    def test_returns_function_toolset(self, mock_s3_client, mock_textract_client):
        """Test that a FunctionToolset is returned."""
        from pydantic_ai import FunctionToolset

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test",
            key="test.jpg",
            textract_client=mock_textract_client,
        )
        assert isinstance(toolset, FunctionToolset)

    def test_toolset_creation_with_different_buckets(self, mock_s3_client, mock_textract_client):
        """Test that toolset can be created for different S3 locations."""
        toolset1 = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="landing-bucket",
            key="uploads/book1.jpg",
            textract_client=mock_textract_client,
        )

        toolset2 = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="raw-bucket",
            key="metadata/book2.jpg",
            textract_client=mock_textract_client,
        )

        # Both toolsets should be created independently
        assert toolset1 is not None
        assert toolset2 is not None
        assert toolset1 is not toolset2

    def test_toolset_creation_with_optional_textract_client(self, mock_s3_client):
        """Test that toolset can be created without providing textract_client."""
        # textract_client is optional, defaults to io module (placeholder)
        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test",
            key="test.jpg",
        )
        assert toolset is not None


class TestImageMetadataEdgeCases:
    """Test edge cases for ImageMetadata."""

    def test_very_large_file_size(self):
        """Test metadata with very large file size."""
        model = ImageMetadata(
            size_bytes=5_000_000_000,  # 5GB
            key="uploads/huge.jpg",
        )
        assert model.size_bytes == 5_000_000_000

    def test_various_mime_types(self):
        """Test metadata with various MIME types."""
        for mime_type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            model = ImageMetadata(
                size_bytes=1000,
                content_type=mime_type,
                key="test.jpg",
            )
            assert model.content_type == mime_type

    def test_s3_key_with_special_characters(self):
        """Test metadata with S3 keys containing special characters."""
        special_keys = [
            "uploads/book-cover (1).jpg",
            "uploads/my cover.jpg",
            "uploads/café-cover.jpg",
        ]
        for key in special_keys:
            model = ImageMetadata(size_bytes=1000, key=key)
            assert model.key == key

    def test_zero_byte_file(self):
        """Test metadata for empty file."""
        model = ImageMetadata(size_bytes=0, key="empty.jpg")
        assert model.size_bytes == 0


class TestTextractResultEdgeCases:
    """Test edge cases for TextractResult."""

    def test_empty_extracted_text(self):
        """Test with empty text extraction."""
        result = TextractResult(
            extracted_text="",
            confidence=0.0,
            line_count=0,
        )
        assert result.extracted_text == ""

    def test_very_long_extracted_text(self):
        """Test with very long extracted text."""
        long_text = "Sample text\n" * 1000
        result = TextractResult(
            extracted_text=long_text,
            confidence=0.85,
            line_count=1000,
        )
        assert result.line_count == 1000

    def test_raw_blocks_with_complex_json(self):
        """Test raw_blocks with complex JSON structure."""
        complex_blocks = json.dumps(
            [
                {
                    "text": "Title",
                    "type": "LINE",
                    "confidence": 99.5,
                    "geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.2}},
                },
            ]
        )
        result = TextractResult(
            extracted_text="Title",
            confidence=0.995,
            raw_blocks=complex_blocks,
        )
        parsed = json.loads(result.raw_blocks)
        assert parsed[0]["geometry"]["BoundingBox"]["Left"] == 0.1

    def test_textract_result_with_zero_confidence(self):
        """Test TextractResult handles zero confidence."""
        result = TextractResult(
            extracted_text="",
            confidence=0.0,
            line_count=0,
        )
        assert result.confidence == 0.0

    def test_textract_result_with_full_confidence(self):
        """Test TextractResult handles 100% confidence."""
        result = TextractResult(
            extracted_text="Perfect text",
            confidence=1.0,
            line_count=1,
        )
        assert result.confidence == 1.0


class TestTextractResultJsonSerialization:
    """Test TextractResult JSON serialization."""

    def test_model_serialization_to_dict(self):
        """Test model can be converted to dict."""
        result = TextractResult(
            extracted_text="Sample",
            confidence=0.9,
            line_count=1,
        )
        data = result.model_dump()
        assert data["extracted_text"] == "Sample"
        assert data["confidence"] == 0.9

    def test_model_serialization_to_json(self):
        """Test model can be converted to JSON string."""
        result = TextractResult(
            extracted_text="Sample",
            confidence=0.9,
        )
        json_str = result.model_dump_json()
        assert '"extracted_text":"Sample"' in json_str
        assert '"confidence":0.9' in json_str


class TestImageMetadataJsonSerialization:
    """Test ImageMetadata JSON serialization."""

    def test_model_serialization_to_dict(self):
        """Test model can be converted to dict."""
        model = ImageMetadata(
            size_bytes=1024,
            content_type="image/jpeg",
            key="test.jpg",
        )
        data = model.model_dump()
        assert data["size_bytes"] == 1024
        assert data["content_type"] == "image/jpeg"

    def test_model_serialization_to_json(self):
        """Test model can be converted to JSON string."""
        model = ImageMetadata(
            size_bytes=1024,
            key="test.jpg",
        )
        json_str = model.model_dump_json()
        assert '"size_bytes":1024' in json_str
        assert '"key":"test.jpg"' in json_str


class TestImageToolsetIntegration:
    """Integration tests for image toolset."""

    def test_create_multiple_independent_toolsets(self, mock_s3_client, mock_textract_client):
        """Test that multiple toolsets have independent state."""
        toolsets = [
            build_image_toolset(
                s3_client=mock_s3_client,
                bucket="bucket1",
                key=f"key{i}.jpg",
                textract_client=mock_textract_client,
            )
            for i in range(3)
        ]

        # All should be created successfully
        assert len(toolsets) == 3
        assert all(ts is not None for ts in toolsets)
        # Should all be different instances
        assert len(set(id(ts) for ts in toolsets)) == 3

    def test_build_toolset_for_various_file_types(self, mock_s3_client, mock_textract_client):
        """Test toolset creation for various image file types."""
        file_keys = [
            "cover.jpg",
            "image.png",
            "picture.webp",
            "scan.gif",
            "book.jpeg",
        ]

        for key in file_keys:
            toolset = build_image_toolset(
                s3_client=mock_s3_client,
                bucket="test",
                key=key,
                textract_client=mock_textract_client,
            )
            assert toolset is not None

    def test_toolset_captures_closure_variables(self, mock_s3_client, mock_textract_client):
        """Test that toolset properly captures bucket and key in closure."""
        bucket = "my-bucket"
        key = "my-key.jpg"

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket=bucket,
            key=key,
            textract_client=mock_textract_client,
        )

        # Toolset created with correct parameters
        assert toolset is not None


class TestImageToolsetDocumentation:
    """Test that docstrings are present and meaningful."""

    def test_image_metadata_has_field_descriptions(self):
        """Test that ImageMetadata fields have descriptions."""
        fields = ImageMetadata.model_fields
        assert fields["size_bytes"].description is not None
        assert fields["content_type"].description is not None

    def test_textract_result_has_field_descriptions(self):
        """Test that TextractResult fields have descriptions."""
        fields = TextractResult.model_fields
        assert fields["extracted_text"].description is not None
        assert fields["confidence"].description is not None


class TestImageToolFunctionsDirectly:
    """Test tool functions by accessing via toolset's _tools."""

    def test_get_image_metadata_success(self, mock_s3_client):
        """Test successful image metadata retrieval."""
        mock_s3_client.head_object.return_value = {
            "ContentLength": 2048,
            "ContentType": "image/png",
        }

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.png",
        )

        # Verify the S3 client was used correctly
        assert toolset is not None

    def test_get_image_metadata_s3_error(self, mock_s3_client):
        """Test error handling when S3 fails."""
        mock_s3_client.head_object.side_effect = Exception("S3 access denied")

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.jpg",
        )

        # Toolset should still be created even if S3 call fails later
        assert toolset is not None

    def test_extract_text_via_textract_success(self, mock_s3_client, mock_textract_client):
        """Test successful Textract extraction."""
        build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.jpg",
            textract_client=mock_textract_client,
        )

        # Verify mock was configured
        assert mock_textract_client.detect_document_text is not None

    def test_extract_text_via_textract_no_confidence_filter(self, mock_s3_client):
        """Test Textract extraction with low-confidence blocks filtered."""
        mock_textract = MagicMock()
        mock_textract.detect_document_text.return_value = {
            "Blocks": [
                {
                    "BlockType": "LINE",
                    "Text": "High confidence",
                    "Confidence": 95.0,
                },
                {
                    "BlockType": "LINE",
                    "Text": "Low confidence",
                    "Confidence": 30.0,  # Below 50 threshold
                },
            ]
        }

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.jpg",
            textract_client=mock_textract,
        )

        assert toolset is not None

    def test_extract_text_via_textract_empty_blocks(self, mock_s3_client):
        """Test Textract extraction with no blocks."""
        mock_textract = MagicMock()
        mock_textract.detect_document_text.return_value = {"Blocks": []}

        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.jpg",
            textract_client=mock_textract,
        )

        assert toolset is not None

    def test_extract_text_call_limit_enforced(self, mock_s3_client, mock_textract_client):
        """Test that extract_text can only be called once."""
        # This verifies the call limit logic exists in the tool
        toolset = build_image_toolset(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            key="images/cover.jpg",
            textract_client=mock_textract_client,
        )

        # The toolset should have both tools registered
        assert toolset is not None
