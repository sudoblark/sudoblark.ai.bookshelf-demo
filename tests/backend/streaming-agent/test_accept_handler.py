"""Tests for accept_handler.py - Save metadata to S3 with Hive partitioning."""

import importlib
import json
import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)
accept_handler_mod = importlib.import_module("accept_handler")
AcceptHandler = accept_handler_mod.AcceptHandler
_sanitise = accept_handler_mod._sanitise


class TestSanitiseFunction:
    """Test the _sanitise helper function for S3 partition values."""

    def test_removes_special_characters(self):
        """Test that special characters are replaced with underscores."""
        assert _sanitise("John@Doe") == "John_Doe"
        assert _sanitise("O'Brien") == "O_Brien"
        assert _sanitise("Smith-Jones") == "Smith-Jones"  # Hyphens are allowed

    def test_preserves_alphanumeric_and_allowed_chars(self):
        """Test that alphanumeric, space, underscore, hyphen, period are preserved."""
        assert _sanitise("John Doe") == "John Doe"
        assert _sanitise("Jane_Smith") == "Jane_Smith"
        assert _sanitise("John-Doe") == "John-Doe"
        assert _sanitise("J.K.Rowling") == "J.K.Rowling"
        assert _sanitise("Author123") == "Author123"

    def test_empty_string_returns_unknown(self):
        """Test that empty string is converted to 'unknown'."""
        assert _sanitise("") == "unknown"

    def test_whitespace_only_returns_unknown(self):
        """Test that whitespace-only string is converted to 'unknown'."""
        assert _sanitise("   ") == "unknown"

    def test_strips_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        assert _sanitise("  John Doe  ") == "John Doe"

    def test_multiple_special_characters(self):
        """Test handling of multiple consecutive special characters."""
        assert _sanitise("###John###") == "___John___"

    def test_unicode_characters_replaced(self):
        """Test that unicode characters are replaced."""
        assert _sanitise("Café") == "Caf_"
        assert _sanitise("München") == "M_nchen"


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def accept_handler(monkeypatch, mock_s3_client):
    """Create AcceptHandler with mocked S3 client."""
    monkeypatch.setenv("RAW_BUCKET", "test-raw-bucket")
    return AcceptHandler(s3_client=mock_s3_client)


@pytest.fixture
def mock_request():
    """Create mock FastAPI Request."""
    request = MagicMock()

    async def json_mock():
        return {}

    request.json = json_mock
    return request


@pytest.fixture
def sample_request_body():
    """Sample request body with metadata."""
    return {
        "metadata": {
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "isbn": "9780743273565",
            "publisher": "Scribner",
            "published_year": 2004,
            "description": "A classic American novel",
            "confidence": 0.95,
        },
        "filename": "cover.jpg",
    }


class TestAcceptHandlerSuccess:
    """Test successful metadata acceptance."""

    @pytest.mark.asyncio
    async def test_returns_200_with_accepted_status(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that handler returns 200 with 'accepted' status."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_returns_saved_key_in_response(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that saved S3 key is returned."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        assert "saved_key" in body
        key = body["saved_key"]
        # Key format: author={author}/published_year={year}/{uuid}.json
        assert key.startswith("author=")
        assert "/published_year=" in key
        assert key.endswith(".json")

    @pytest.mark.asyncio
    async def test_returns_upload_id_in_response(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that upload_id is returned."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        assert "upload_id" in body
        # Verify it's a valid UUID
        try:
            uuid.UUID(body["upload_id"])
            assert True
        except ValueError:
            pytest.fail(f"upload_id {body['upload_id']} is not a valid UUID")

    @pytest.mark.asyncio
    async def test_key_format_includes_author_and_year(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that S3 key follows Hive partition format."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        key = body["saved_key"]

        assert "author=F. Scott Fitzgerald" in key
        assert "published_year=2004" in key
        assert key.endswith(".json")

    @pytest.mark.asyncio
    async def test_s3_put_object_called_with_correct_params(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that S3 put_object is called with correct bucket and key."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        await accept_handler.handle(mock_request)

        mock_s3_client.put_object.assert_called_once()
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-raw-bucket"
        assert call_kwargs["ContentType"] == "application/json"
        assert "author=" in call_kwargs["Key"]

    @pytest.mark.asyncio
    async def test_metadata_is_persisted_as_json(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that metadata is written as JSON to S3."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        await accept_handler.handle(mock_request)

        # Get the Body from put_object call
        call_kwargs = mock_s3_client.put_object.call_args[1]
        payload = call_kwargs["Body"]

        # Verify it's valid JSON
        data = json.loads(payload)
        assert data["title"] == "The Great Gatsby"
        assert data["author"] == "F. Scott Fitzgerald"
        assert data["filename"] == "cover.jpg"


class TestAcceptHandlerPartitioning:
    """Test Hive-style partitioning logic."""

    @pytest.mark.asyncio
    async def test_sanitizes_author_in_key(self, accept_handler, mock_request, sample_request_body):
        """Test that author is sanitized in the S3 key."""
        sample_request_body["metadata"]["author"] = "O'Brien@Smith"

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        key = body["saved_key"]
        # Special characters should be replaced
        assert "O_Brien_Smith" in key

    @pytest.mark.asyncio
    async def test_missing_author_defaults_to_unknown(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that missing author defaults to 'unknown' in key."""
        del sample_request_body["metadata"]["author"]

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        key = body["saved_key"]
        assert "author=unknown" in key

    @pytest.mark.asyncio
    async def test_missing_year_defaults_to_unknown(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that missing published_year defaults to 'unknown' in key."""
        sample_request_body["metadata"]["published_year"] = None

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        key = body["saved_key"]
        assert "published_year=unknown" in key

    @pytest.mark.asyncio
    async def test_key_format_with_all_sanitization(self, accept_handler, mock_request):
        """Test full key format with both author and year."""
        body = {
            "metadata": {
                "title": "Test",
                "author": "Smith, Jr.",
                "published_year": 1999,
            },
            "filename": "test.jpg",
        }

        async def json_mock():
            return body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        response_body = json.loads(resp.body.decode())
        key = response_body["saved_key"]

        # Verify format: author={sanitized_author}/published_year={year}/{uuid}.json
        assert key.startswith("author=")
        assert "/published_year=" in key
        assert "Smith_ Jr." in key  # Comma replaced, space and period kept
        assert "published_year=1999" in key


class TestAcceptHandlerValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_returns_400_when_metadata_missing(self, accept_handler, mock_request):
        """Test that handler returns 400 when metadata is missing."""

        async def json_mock():
            return {"filename": "test.jpg"}

        mock_request.json = json_mock

        with pytest.raises(HTTPException) as exc:
            await accept_handler.handle(mock_request)
        assert exc.value.status_code == 400
        assert "metadata" in str(exc.value.detail).lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_metadata_is_none(self, accept_handler, mock_request):
        """Test that handler returns 400 when metadata is None."""

        async def json_mock():
            return {"metadata": None}

        mock_request.json = json_mock

        with pytest.raises(HTTPException) as exc:
            await accept_handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_body_invalid_json(self, accept_handler, mock_request):
        """Test that handler returns 400 when body is invalid JSON."""

        async def json_mock():
            raise ValueError("Invalid JSON")

        mock_request.json = json_mock

        with pytest.raises(HTTPException) as exc:
            await accept_handler.handle(mock_request)
        assert exc.value.status_code == 400
        assert "JSON" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_filename_defaults_to_unknown(
        self, accept_handler, mock_request, sample_request_body
    ):
        """Test that missing filename defaults to 'unknown'."""
        del sample_request_body["filename"]

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["status"] == "accepted"


class TestAcceptHandlerErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_returns_500_when_s3_put_fails(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that handler returns 500 when S3 put_object fails."""
        mock_s3_client.put_object.side_effect = Exception("S3 error")

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock

        with pytest.raises(HTTPException) as exc:
            await accept_handler.handle(mock_request)
        assert exc.value.status_code == 500
        assert "save" in str(exc.value.detail).lower()

    @pytest.mark.asyncio
    async def test_returns_500_on_s3_connection_error(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that handler returns 500 on S3 connection errors."""
        mock_s3_client.put_object.side_effect = ConnectionError("S3 unreachable")

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock

        with pytest.raises(HTTPException) as exc:
            await accept_handler.handle(mock_request)
        assert exc.value.status_code == 500


class TestAcceptHandlerMetadataHandling:
    """Test metadata field handling and JSON serialization."""

    @pytest.mark.asyncio
    async def test_includes_all_metadata_fields_in_json(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that all metadata fields are included in persisted JSON."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        await accept_handler.handle(mock_request)

        call_kwargs = mock_s3_client.put_object.call_args[1]
        payload = call_kwargs["Body"]
        data = json.loads(payload)

        # Verify all metadata fields are present
        for key, value in sample_request_body["metadata"].items():
            assert data[key] == value

    @pytest.mark.asyncio
    async def test_includes_filename_and_upload_id_in_json(
        self, accept_handler, mock_request, sample_request_body, mock_s3_client
    ):
        """Test that filename and upload_id are included in JSON."""

        async def json_mock():
            return sample_request_body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        call_kwargs = mock_s3_client.put_object.call_args[1]
        payload = call_kwargs["Body"]
        data = json.loads(payload)

        response_body = json.loads(resp.body.decode())

        assert data["filename"] == "cover.jpg"
        assert data["upload_id"] == response_body["upload_id"]

    @pytest.mark.asyncio
    async def test_uses_default_str_for_serialization(
        self, accept_handler, mock_request, mock_s3_client
    ):
        """Test that non-JSON-serializable objects are converted to string."""
        from decimal import Decimal

        body = {
            "metadata": {
                "title": "Test",
                "confidence": Decimal("0.95"),  # Not directly JSON serializable
            },
        }

        async def json_mock():
            return body

        mock_request.json = json_mock
        resp = await accept_handler.handle(mock_request)

        assert resp.status_code == 200
        # Verify it serialized successfully
        body = json.loads(resp.body.decode())
        assert body["status"] == "accepted"
