"""Handler for Ook Chat — general AI chat about user's bookshelf."""

import json
import logging
import os
from typing import Any, AsyncGenerator, Optional

import boto3
from bookshelf_handler import BookshelfHandler
from bookshelf_streaming_agent import BookshelfStreamingAgent
from bookshelf_toolset import build_bookshelf_toolset
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from streaming_models import StreamingAgentResponse
from tool_tracker import ToolTracker

logger = logging.getLogger(__name__)

# In-memory session storage for message history
# Key: session_id, Value: list of ModelMessage objects
_session_history: dict[str, list] = {}

# Ook system prompt - friendly bookshelf assistant
OOK_SYSTEM_PROMPT = """\
You are Ook, a friendly AI assistant that helps users explore their book collection.

You have access to tools to query the user's bookshelf:
- list_books: Get all books
- search_books: Search by title or author
- get_overview: Get stats (total books, most common author)

When the user asks a question:
1. Use tools to query their bookshelf
2. Answer conversationally based on the data
3. Be concise but friendly (2-4 sentences)
4. If no relevant books found, say so honestly

Examples:
- "What fantasy books do I have?" → search_books("fantasy", "title")
- "Who's my most prolific author?" → get_overview()
- "Tell me about Sanderson books" → search_books("Sanderson", "author")
"""


class OokHandler:
    """Handles Ook Chat streaming conversation."""

    def __init__(
        self,
        agent: Optional[BookshelfStreamingAgent] = None,
        s3_client: Any = None,
        tracker: Optional[ToolTracker] = None,
    ) -> None:
        self._model_id: str = os.environ["BEDROCK_MODEL_ID"]
        region: str = os.environ.get(
            "BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
        )
        self._s3 = s3_client or boto3.client("s3")
        self._tracker = tracker or ToolTracker()

        # Create BookshelfHandler for toolset
        self._bookshelf_handler = BookshelfHandler(s3_client=self._s3)

        # Build toolset with tracker
        self._toolset = build_bookshelf_toolset(self._bookshelf_handler, tracker=self._tracker)

        # Initialize agent with custom Ook prompt and structured output for tool usage
        if agent is None:
            bedrock_client = boto3.client("bedrock-runtime", region_name=region)
            self._agent = BookshelfStreamingAgent(
                model_id=self._model_id,
                bedrock_client=bedrock_client,
                system_prompt=OOK_SYSTEM_PROMPT,
                output_type=StreamingAgentResponse,
            )
        else:
            self._agent = agent

    async def handle(self, request: Request) -> StreamingResponse:
        """Handle POST /api/ook/chat with streaming SSE response."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        session_id: Optional[str] = body.get("session_id")
        message: Optional[str] = body.get("message")

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")

        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        return StreamingResponse(
            self._stream_events(session_id, message),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    async def _stream_events(
        self, session_id: str, message: str
    ) -> AsyncGenerator[str, None]:  # pragma: no cover
        """Stream SSE events for Ook chat."""
        # Get or initialize session history
        message_history = _session_history.get(session_id, [])
        prev_msg = ""

        # Reset tracker for this request
        self._tracker.clear()

        try:
            async with self._agent.run_stream(
                message,
                toolsets=[self._toolset],
                message_history=message_history if message_history else None,
            ) as result:
                # Stream structured output with tool usage
                async for partial in result.stream_output():
                    # Stream message deltas
                    current_msg: str = partial.message or ""
                    if len(current_msg) > len(prev_msg):
                        yield _sse("text_delta", {"delta": current_msg[len(prev_msg) :]})
                        prev_msg = current_msg

                    # Stream tools_used list when it changes
                    if partial.tools_used:
                        yield _sse("tools_used", {"tools": partial.tools_used})

                # After stream completes, emit tool execution details
                tool_executions = self._tracker.get_executions()
                if tool_executions:
                    yield _sse(
                        "tool_executions",
                        {"executions": [exec.model_dump() for exec in tool_executions]},
                    )

                # Store updated message history
                _session_history[session_id] = result.all_messages()

        except Exception as exc:
            logger.exception("Agent stream error in Ook chat: %s", exc)
            yield _sse("error", {"message": "Chat error — please try again"})
            return

        yield _sse("complete", {})


def _sse(event_type: str, data: dict) -> str:
    """Format SSE event."""
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
