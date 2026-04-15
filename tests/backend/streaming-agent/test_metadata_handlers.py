"""Tests for metadata handlers - SSE streaming orchestration."""

import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)

# Set required environment variables
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("BEDROCK_REGION", "eu-west-2")

initial_mod = importlib.import_module("metadata_initial_handler")
refine_mod = importlib.import_module("metadata_refine_handler")

MetadataInitialHandler = initial_mod.MetadataInitialHandler
MetadataRefineHandler = refine_mod.MetadataRefineHandler
_sse_initial = initial_mod._sse
_sse_refine = refine_mod._sse


class TestSSEFormatter:
    """Test SSE event formatting helper."""

    def test_sse_formats_text_delta(self):
        """Test SSE formatting for text_delta event."""
        result = _sse_initial("text_delta", {"delta": "Hello"})
        assert "data: " in result
        assert result.endswith("\n\n")
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed["type"] == "text_delta"
        assert parsed["delta"] == "Hello"

    def test_sse_formats_metadata_update(self):
        """Test SSE formatting for metadata_update event."""
        result = _sse_initial("metadata_update", {"field": "title", "value": "Test Book"})
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed["type"] == "metadata_update"
        assert parsed["field"] == "title"
        assert parsed["value"] == "Test Book"

    def test_sse_formats_complete(self):
        """Test SSE formatting for complete event."""
        result = _sse_initial("complete", {})
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed["type"] == "complete"

    def test_sse_formats_error(self):
        """Test SSE formatting for error event."""
        result = _sse_initial("error", {"message": "Something went wrong"})
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed["type"] == "error"
        assert parsed["message"] == "Something went wrong"

    def test_sse_ends_with_double_newline(self):
        """Test that SSE event ends with double newline."""
        result = _sse_initial("text_delta", {"delta": "test"})
        assert result.endswith("\n\n")

    def test_sse_valid_json_payload(self):
        """Test that SSE payload is valid JSON."""
        result = _sse_initial("metadata_update", {"field": "author", "value": "John Doe"})
        data_part = result.split("data: ")[1].strip()
        # Should not raise
        json.loads(data_part)


class TestMetadataInitialHandler:
    """Test MetadataInitialHandler request parsing and error handling."""

    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    def test_handler_initialization(self, mock_agent_class, mock_boto3):
        """Test handler initialization."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        assert handler is not None
        assert handler._agent == mock_agent_instance

    @pytest.mark.asyncio
    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    async def test_handle_invalid_json_body(self, mock_agent_class, mock_boto3):
        """Test that invalid JSON raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        mock_request = AsyncMock()
        mock_request.json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    async def test_handle_missing_bucket(self, mock_agent_class, mock_boto3):
        """Test that missing bucket raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {"key": "test.jpg"}

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    async def test_handle_missing_key(self, mock_agent_class, mock_boto3):
        """Test that missing key raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {"bucket": "test-bucket"}

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    async def test_handle_valid_request(self, mock_agent_class, mock_boto3):
        """Test valid request handling."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {
            "bucket": "test-bucket",
            "key": "test.jpg",
            "filename": "cover.jpg",
        }

        response = await handler.handle(mock_request)

        # Should return StreamingResponse
        from fastapi.responses import StreamingResponse

        assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    @patch("metadata_initial_handler.boto3.client")
    @patch("metadata_initial_handler.BookshelfStreamingAgent")
    async def test_handle_filename_defaults(self, mock_agent_class, mock_boto3):
        """Test that filename defaults to 'book cover'."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataInitialHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {
            "bucket": "test-bucket",
            "key": "test.jpg",
        }

        response = await handler.handle(mock_request)

        # Should still succeed with default filename
        from fastapi.responses import StreamingResponse

        assert isinstance(response, StreamingResponse)

    def test_initial_handler_with_custom_agent(self):
        """Test creating handler with custom agent."""
        custom_agent = MagicMock()
        handler = MetadataInitialHandler(agent=custom_agent)
        assert handler._agent == custom_agent

    def test_initial_handler_response_headers(self):
        """Test that streaming response has correct headers."""
        with patch("metadata_initial_handler.boto3.client"):
            with patch("metadata_initial_handler.BookshelfStreamingAgent"):
                handler = MetadataInitialHandler()

                import asyncio

                async def test_headers():
                    mock_request = AsyncMock()
                    mock_request.json.return_value = {
                        "bucket": "test-bucket",
                        "key": "test.jpg",
                    }

                    response = await handler.handle(mock_request)

                    # Verify SSE headers
                    assert response.media_type == "text/event-stream"
                    assert response.headers["X-Accel-Buffering"] == "no"
                    assert response.headers["Cache-Control"] == "no-cache"

                asyncio.run(test_headers())


class TestMetadataRefineHandler:
    """Test MetadataRefineHandler request parsing and error handling."""

    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    def test_handler_initialization(self, mock_agent_class, mock_boto3):
        """Test handler initialization."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        assert handler is not None
        assert handler._agent == mock_agent_instance

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_invalid_json_body(self, mock_agent_class, mock_boto3):
        """Test that invalid JSON raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        mock_request = AsyncMock()
        mock_request.json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_missing_session_id(self, mock_agent_class, mock_boto3):
        """Test that missing session_id raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {"message": "Update title"}

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_missing_message(self, mock_agent_class, mock_boto3):
        """Test that missing message raises HTTPException."""
        from fastapi import HTTPException

        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {"session_id": "session-123"}

        with pytest.raises(HTTPException) as exc:
            await handler.handle(mock_request)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_valid_request(self, mock_agent_class, mock_boto3):
        """Test valid request handling."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {
            "session_id": "session-123",
            "message": "Update the title to Test Book",
        }

        response = await handler.handle(mock_request)

        # Should return StreamingResponse
        from fastapi.responses import StreamingResponse

        assert isinstance(response, StreamingResponse)

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_current_metadata_defaults(self, mock_agent_class, mock_boto3):
        """Test that current_metadata defaults to empty dict."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        mock_request = AsyncMock()
        mock_request.json.return_value = {
            "session_id": "session-123",
            "message": "Test message",
        }

        response = await handler.handle(mock_request)

        # Should still succeed with default metadata
        from fastapi.responses import StreamingResponse

        assert isinstance(response, StreamingResponse)

    def test_refine_handler_with_custom_agent(self):
        """Test creating handler with custom agent."""
        custom_agent = MagicMock()
        handler = MetadataRefineHandler(agent=custom_agent)
        assert handler._agent == custom_agent

    def test_refine_handler_response_headers(self):
        """Test that streaming response has correct headers."""
        with patch("metadata_refine_handler.boto3.client"):
            with patch("metadata_refine_handler.BookshelfStreamingAgent"):
                handler = MetadataRefineHandler()

                import asyncio

                async def test_headers():
                    mock_request = AsyncMock()
                    mock_request.json.return_value = {
                        "session_id": "session-123",
                        "message": "Test message",
                    }

                    response = await handler.handle(mock_request)

                    # Verify SSE headers
                    assert response.media_type == "text/event-stream"
                    assert response.headers["X-Accel-Buffering"] == "no"
                    assert response.headers["Cache-Control"] == "no-cache"

                asyncio.run(test_headers())

    @pytest.mark.asyncio
    @patch("metadata_refine_handler.boto3.client")
    @patch("metadata_refine_handler.BookshelfStreamingAgent")
    async def test_handle_preserves_prompt_structure(self, mock_agent_class, mock_boto3):
        """Test that prompt is correctly structured with metadata and message."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        handler = MetadataRefineHandler()

        current_metadata = {"title": "Current Title", "author": "Author Name"}

        mock_request = AsyncMock()
        mock_request.json.return_value = {
            "session_id": "session-123",
            "message": "Change title to New Title",
            "current_metadata": current_metadata,
        }

        response = await handler.handle(mock_request)

        # Should succeed and return streaming response
        from fastapi.responses import StreamingResponse

        assert isinstance(response, StreamingResponse)


class TestMetadataFieldHandling:
    """Test metadata field constant definitions."""

    def test_initial_metadata_fields_constant(self):
        """Test that metadata fields are defined in initial handler."""
        assert hasattr(initial_mod, "_METADATA_FIELDS")
        fields = initial_mod._METADATA_FIELDS
        assert "title" in fields
        assert "author" in fields
        assert "isbn" in fields
        assert "publisher" in fields
        assert "published_year" in fields
        assert "description" in fields
        assert "confidence" in fields

    def test_refine_metadata_fields_constant(self):
        """Test that metadata fields are defined in refine handler."""
        assert hasattr(refine_mod, "_METADATA_FIELDS")
        fields = refine_mod._METADATA_FIELDS
        assert "title" in fields
        assert "author" in fields
        assert "isbn" in fields

    def test_metadata_fields_match_between_handlers(self):
        """Test that both handlers use same metadata fields."""
        assert initial_mod._METADATA_FIELDS == refine_mod._METADATA_FIELDS


class TestSessionHistory:
    """Test session history management in refine handler."""

    def test_session_history_module_variable_exists(self):
        """Test that _session_history module variable exists."""
        assert hasattr(refine_mod, "_session_history")

    def test_session_history_is_dict(self):
        """Test that _session_history is a dictionary."""
        assert isinstance(refine_mod._session_history, dict)

    def test_refinement_mode_flag(self):
        """Test that refine handler creates refinement mode agent."""
        with patch("metadata_refine_handler.boto3.client"):
            with patch("metadata_refine_handler.BookshelfStreamingAgent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                mock_agent_class.return_value = mock_agent_instance

                MetadataRefineHandler()

                # Verify agent was created with refinement=True
                call_kwargs = mock_agent_class.call_args[1]
                assert call_kwargs.get("refinement") is True
