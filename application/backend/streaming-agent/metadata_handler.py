"""Handler for unified metadata extraction and refinement.

Replaces separate metadata_initial_handler and metadata_refine_handler.
Uses agent with toolsets (similar to Ook Chat pattern) rather than upfront
extraction, giving the agent full agency over when to extract/lookup data.

Session flow:
1. User uploads book cover → client calls with initial message "Extract metadata"
2. Handler creates session, agent calls extraction tools automatically
3. Agent responds conversationally with findings
4. User sends refinement message → handler loads session history
5. Agent accepts corrections, calls update tools, responds
6. Process repeats until user saves
"""

import json
import logging
import os
from typing import Any, AsyncGenerator, Optional

import boto3
from bookshelf_streaming_agent import BookshelfStreamingAgent
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from metadata_toolset import build_metadata_toolset
from streaming_models import StreamingAgentResponse
from tool_tracker import ToolTracker

logger = logging.getLogger(__name__)

# In-memory session storage for message history
# Key: session_id, Value: list of ModelMessage objects
_session_history: dict[str, list] = {}

# Metadata extraction system prompt
METADATA_SYSTEM_PROMPT = """\
You are cataloging books from cover images.

You have access to tools to extract and update metadata:
- extract_ocr_text: Extract text from cover images
- extract_isbn: Find ISBN patterns in text
- lookup_isbn_metadata: Look up book details by ISBN
- lookup_by_title_author: Look up by title/author (fallback)
- update_metadata_field: Populate discovered metadata fields (title, author, isbn, publisher, etc)

Extract metadata and use update_metadata_field to populate the UI with your findings.
Present results conversationally and accept user corrections. Be concise and friendly.
"""


class MetadataHandler:
    """Handles metadata extraction and refinement with full tool agency."""

    def __init__(
        self,
        agent: Optional[BookshelfStreamingAgent] = None,
        s3_client: Any = None,
        textract_client: Any = None,
        tracker: Optional[ToolTracker] = None,
    ) -> None:
        self._model_id: str = os.environ["BEDROCK_MODEL_ID"]
        region: str = os.environ.get(
            "BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
        )
        self._s3 = s3_client or boto3.client("s3")
        self._textract = textract_client or boto3.client("textract", region_name=region)
        self._tracker = tracker or ToolTracker()

        # Initialize agent with metadata extraction prompt and structured output for tool tracking
        if agent is None:
            bedrock_client = boto3.client("bedrock-runtime", region_name=region)
            self._agent = BookshelfStreamingAgent(
                model_id=self._model_id,
                bedrock_client=bedrock_client,
                system_prompt=METADATA_SYSTEM_PROMPT,
                output_type=StreamingAgentResponse,
            )
        else:
            self._agent = agent

    async def handle(self, request: Request) -> StreamingResponse:
        """Handle POST /api/metadata/extract with streaming SSE response."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        session_id: Optional[str] = body.get("session_id")
        message: Optional[str] = body.get("message")
        bucket: Optional[str] = body.get("bucket")  # For initial extraction
        key: Optional[str] = body.get("key")  # For initial extraction

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        return StreamingResponse(
            self._stream_events(session_id, message, bucket, key),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    async def _stream_events(  # pragma: no cover
        self,
        session_id: str,
        message: str,
        bucket: Optional[str] = None,
        key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream SSE events for metadata extraction."""
        # Get or initialize session history
        message_history = _session_history.get(session_id, [])
        prev_msg = ""

        # Reset tracker for this request
        self._tracker.clear()

        try:
            # Build toolset for this session
            # For initial extraction, toolset gets bucket/key
            # For refinement, toolset can still use tools but bucket/key are None
            if bucket and key:
                toolset = build_metadata_toolset(
                    s3_client=self._s3,
                    textract_client=self._textract,
                    bucket=bucket,
                    key=key,
                    tracker=self._tracker,
                )
            else:
                # For refinement messages (no bucket/key), still create toolset but
                # extraction tools will fail gracefully
                toolset = build_metadata_toolset(
                    s3_client=self._s3,
                    textract_client=self._textract,
                    bucket="",
                    key="",
                    tracker=self._tracker,
                )

            async with self._agent.run_stream(
                message,
                toolsets=[toolset],
                message_history=message_history if message_history else None,
            ) as result:
                # Stream structured output with proper tool execution handling
                async for partial in result.stream_output():
                    # Stream message deltas as they accumulate
                    current_msg: str = partial.message or ""
                    if len(current_msg) > len(prev_msg):
                        yield _sse("text_delta", {"delta": current_msg[len(prev_msg) :]})
                        prev_msg = current_msg

                # After stream completes, emit tool execution details
                tool_executions = self._tracker.get_executions()
                if tool_executions:
                    yield _sse(
                        "tool_executions",
                        {"executions": [exec.model_dump() for exec in tool_executions]},
                    )

                # Store updated message history for next turn
                _session_history[session_id] = result.all_messages()

        except Exception as exc:
            logger.exception("Agent stream error in metadata extraction: %s", exc)
            yield _sse("error", {"message": "Extraction error — please try again"})
            return

        yield _sse("complete", {})


def _sse(event_type: str, data: dict) -> str:
    """Format SSE event."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
