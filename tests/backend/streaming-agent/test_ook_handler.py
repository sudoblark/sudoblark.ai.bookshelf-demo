"""Tests for Ook chat handler."""

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Setup path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent / "application/backend/streaming-agent"),
)

os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")
os.environ.setdefault("BEDROCK_REGION", "eu-west-2")

ook_mod = importlib.import_module("ook_handler")
OokHandler = ook_mod.OokHandler


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_handle_invalid_json(mock_toolset, mock_boto3):
    """Test that invalid JSON raises HTTPException."""
    from fastapi import HTTPException

    handler = OokHandler()

    mock_request = AsyncMock()
    mock_request.json.side_effect = ValueError("Invalid JSON")

    with pytest.raises(HTTPException) as exc:
        await handler.handle(mock_request)
    assert exc.value.status_code == 400
    assert "Invalid JSON" in exc.value.detail


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_handle_missing_session_id(mock_toolset, mock_boto3):
    """Test that missing session_id raises HTTPException."""
    from fastapi import HTTPException

    handler = OokHandler()

    mock_request = AsyncMock()
    mock_request.json.return_value = {"message": "Hello"}

    with pytest.raises(HTTPException) as exc:
        await handler.handle(mock_request)
    assert exc.value.status_code == 400
    assert "session_id" in exc.value.detail


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_handle_missing_message(mock_toolset, mock_boto3):
    """Test that missing message raises HTTPException."""
    from fastapi import HTTPException

    handler = OokHandler()

    mock_request = AsyncMock()
    mock_request.json.return_value = {"session_id": "session-123"}

    with pytest.raises(HTTPException) as exc:
        await handler.handle(mock_request)
    assert exc.value.status_code == 400
    assert "message" in exc.value.detail


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_handle_valid_request(mock_toolset, mock_boto3):
    """Test valid request returns StreamingResponse."""
    from fastapi.responses import StreamingResponse

    handler = OokHandler()

    mock_request = AsyncMock()
    mock_request.json.return_value = {
        "session_id": "session-123",
        "message": "What books do I have?",
    }

    response = await handler.handle(mock_request)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers["X-Accel-Buffering"] == "no"
    assert response.headers["Cache-Control"] == "no-cache"


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_sse_text_delta_format(mock_toolset, mock_boto3):
    """Test SSE text_delta event formatting."""
    result = ook_mod._sse("text_delta", {"delta": "Hello"})

    assert "data: " in result
    assert result.endswith("\n\n")

    parsed = json.loads(result.split("data: ")[1].strip())
    assert parsed["type"] == "text_delta"
    assert parsed["delta"] == "Hello"


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_sse_complete_format(mock_toolset, mock_boto3):
    """Test SSE complete event formatting."""
    result = ook_mod._sse("complete", {})

    parsed = json.loads(result.split("data: ")[1].strip())
    assert parsed["type"] == "complete"


@pytest.mark.asyncio
@patch("ook_handler.boto3.client")
@patch("ook_handler.build_bookshelf_toolset")
async def test_sse_error_format(mock_toolset, mock_boto3):
    """Test SSE error event formatting."""
    result = ook_mod._sse("error", {"message": "Something went wrong"})

    parsed = json.loads(result.split("data: ")[1].strip())
    assert parsed["type"] == "error"
    assert parsed["message"] == "Something went wrong"


def test_session_history_initialized():
    """Test that session history is initialized as empty dict."""
    # Access the module-level _session_history variable
    assert isinstance(ook_mod._session_history, dict)
    assert len(ook_mod._session_history) == 0


def test_ook_system_prompt_defined():
    """Test that OOK_SYSTEM_PROMPT is defined and contains expected text."""
    prompt = ook_mod.OOK_SYSTEM_PROMPT
    assert "Ook" in prompt
    assert "list_books" in prompt
    assert "search_books" in prompt
    assert "get_overview" in prompt
