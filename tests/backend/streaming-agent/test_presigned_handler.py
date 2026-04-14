"""Tests for presigned_handler.py - S3 pre-signed URL generation."""

import importlib
import json
import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)
presigned_handler_mod = importlib.import_module("presigned_handler")
PresignedUrlHandler = presigned_handler_mod.PresignedUrlHandler


@pytest.fixture
def mock_s3_client():
    """Mock S3 client with generate_presigned_url."""
    mock = MagicMock()
    mock.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/presigned-url"
    return mock


@pytest.fixture
def presigned_handler(monkeypatch, mock_s3_client):
    """Create PresignedUrlHandler with mocked S3 client."""
    monkeypatch.setenv("LANDING_BUCKET", "test-landing-bucket")
    return PresignedUrlHandler(s3_client=mock_s3_client)


@pytest.fixture
def mock_request():
    """Create mock FastAPI Request."""
    return MagicMock()


class TestPresignedUrlHandlerSuccess:
    """Test successful presigned URL generation."""

    @pytest.mark.asyncio
    async def test_returns_200_with_presigned_url(self, presigned_handler, mock_request):
        """Test that handler returns 200 with valid presigned URL."""
        mock_request.query_params.get.return_value = "cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert "url" in body
        assert body["url"] == "https://test-bucket.s3.amazonaws.com/presigned-url"

    @pytest.mark.asyncio
    async def test_returns_s3_key_in_response(self, presigned_handler, mock_request):
        """Test that S3 key is returned in response."""
        mock_request.query_params.get.return_value = "cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        assert "key" in body
        # Key format: ui/uploads/{session_id}/{filename}
        assert body["key"].startswith("ui/uploads/")
        assert body["key"].endswith("/cover.jpg")

    @pytest.mark.asyncio
    async def test_returns_bucket_name_in_response(self, presigned_handler, mock_request):
        """Test that bucket name is returned in response."""
        mock_request.query_params.get.return_value = "cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        assert body["bucket"] == "test-landing-bucket"

    @pytest.mark.asyncio
    async def test_returns_session_id_as_uuid(self, presigned_handler, mock_request):
        """Test that session_id is a valid UUID."""
        mock_request.query_params.get.return_value = "cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        assert "session_id" in body
        # Verify it's a valid UUID string
        try:
            uuid.UUID(body["session_id"])
            assert True
        except ValueError:
            pytest.fail(f"session_id {body['session_id']} is not a valid UUID")

    @pytest.mark.asyncio
    async def test_multiple_calls_generate_different_session_ids(
        self, presigned_handler, mock_request
    ):
        """Test that each call generates a different session_id."""
        mock_request.query_params.get.return_value = "cover.jpg"

        resp1 = await presigned_handler.handle(mock_request)
        resp2 = await presigned_handler.handle(mock_request)

        body1 = json.loads(resp1.body.decode())
        body2 = json.loads(resp2.body.decode())

        assert body1["session_id"] != body2["session_id"]

    @pytest.mark.asyncio
    async def test_s3_key_contains_session_id(self, presigned_handler, mock_request):
        """Test that S3 key contains the session_id."""
        mock_request.query_params.get.return_value = "cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        key = body["key"]
        session_id = body["session_id"]

        assert session_id in key
        assert key == f"ui/uploads/{session_id}/cover.jpg"

    @pytest.mark.asyncio
    async def test_url_expiry_is_3600_seconds(
        self, presigned_handler, mock_request, mock_s3_client
    ):
        """Test that S3 presigned URL is generated with 3600 second expiry."""
        mock_request.query_params.get.return_value = "cover.jpg"
        await presigned_handler.handle(mock_request)

        # Verify generate_presigned_url was called with ExpiresIn=3600
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 3600

    @pytest.mark.asyncio
    async def test_s3_is_called_with_correct_bucket_and_key(
        self, presigned_handler, mock_request, mock_s3_client
    ):
        """Test that S3 client is called with correct bucket and key."""
        mock_request.query_params.get.return_value = "my-book.png"
        resp = await presigned_handler.handle(mock_request)

        body = json.loads(resp.body.decode())
        expected_key = body["key"]

        mock_s3_client.generate_presigned_url.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["Params"]["Bucket"] == "test-landing-bucket"
        assert call_kwargs["Params"]["Key"] == expected_key


class TestPresignedUrlHandlerValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_returns_400_when_filename_missing(self, presigned_handler, mock_request):
        """Test that handler returns 400 when filename is missing."""
        mock_request.query_params.get.return_value = ""
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 400
        body = json.loads(resp.body.decode())
        assert "error" in body
        assert "filename" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_when_filename_is_empty_in_params(
        self, presigned_handler, mock_request
    ):
        """Test that handler returns 400 when filename is empty in query params."""

        # Mock the .get method with proper default behavior
        def get_side_effect(key, default=""):
            if key == "filename":
                return default  # Returns empty string
            return None

        mock_request.query_params.get.side_effect = get_side_effect
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 400
        body = json.loads(resp.body.decode())
        assert "error" in body

    @pytest.mark.asyncio
    async def test_returns_400_when_filename_is_whitespace(self, presigned_handler, mock_request):
        """Test that handler returns 400 when filename is only whitespace."""
        mock_request.query_params.get.return_value = "   "
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 400
        body = json.loads(resp.body.decode())
        assert "error" in body

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_filename(self, presigned_handler, mock_request):
        """Test that whitespace is stripped from filename."""
        mock_request.query_params.get.return_value = "  cover.jpg  "
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["key"].endswith("/cover.jpg")  # No extra spaces

    @pytest.mark.asyncio
    async def test_accepts_various_filename_formats(self, presigned_handler, mock_request):
        """Test that handler accepts various filename formats."""
        test_filenames = [
            "cover.jpg",
            "book-cover.png",
            "cover_image.jpeg",
            "file123.gif",
            "my.cover.file.webp",
        ]

        for filename in test_filenames:
            mock_request.query_params.get.return_value = filename
            resp = await presigned_handler.handle(mock_request)
            assert resp.status_code == 200
            body = json.loads(resp.body.decode())
            assert body["key"].endswith(f"/{filename}")


class TestPresignedUrlHandlerErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_returns_500_when_s3_generate_fails(
        self, presigned_handler, mock_request, mock_s3_client
    ):
        """Test that handler returns 500 when S3 call fails."""
        mock_s3_client.generate_presigned_url.side_effect = Exception("S3 error")
        mock_request.query_params.get.return_value = "cover.jpg"

        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 500
        body = json.loads(resp.body.decode())
        assert "error" in body
        assert "upload" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_500_on_generic_exception(
        self, presigned_handler, mock_request, mock_s3_client
    ):
        """Test that handler returns 500 on any exception."""
        mock_s3_client.generate_presigned_url.side_effect = RuntimeError("Unexpected error")
        mock_request.query_params.get.return_value = "cover.jpg"

        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 500
        body = json.loads(resp.body.decode())
        assert "error" in body


class TestPresignedUrlHandlerEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_filename_with_special_characters(self, presigned_handler, mock_request):
        """Test that handler handles filenames with special characters."""
        mock_request.query_params.get.return_value = "cover-image (1).jpg"
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert "cover-image (1).jpg" in body["key"]

    @pytest.mark.asyncio
    async def test_filename_with_unicode(self, presigned_handler, mock_request):
        """Test that handler handles unicode filenames."""
        mock_request.query_params.get.return_value = "café-cover.jpg"
        resp = await presigned_handler.handle(mock_request)

        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert "key" in body

    @pytest.mark.asyncio
    async def test_very_long_filename(self, presigned_handler, mock_request):
        """Test that handler handles very long filenames."""
        long_filename = "a" * 200 + ".jpg"
        mock_request.query_params.get.return_value = long_filename
        resp = await presigned_handler.handle(mock_request)

        # Handler should accept it; S3 limits are checked by S3
        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert long_filename in body["key"]
