"""Orchestration layer for POST /api/metadata/refine.

Handles ongoing user conversation to refine book metadata.  On each request:

1. Fetches prior pydantic-ai ``ModelMessage`` history from the in-memory store.
2. Builds a prompt from the user's message and current metadata state.
3. Streams the refinement agent's response as SSE.
4. Persists ``result.all_messages()`` back to the in-memory store so the next
   turn has full context.

Conversation history is keyed by ``session_id`` (the UUID returned by
``/api/upload/presigned``).  History is stored in process memory — suitable
for a local development server; a production deployment would use DynamoDB.

SSE event types emitted
-----------------------
text_delta       ``{"type": "text_delta", "delta": "<text>"}``
metadata_update  ``{"type": "metadata_update", "field": "<name>", "value": <val>}``
complete         ``{"type": "complete"}``
error            ``{"type": "error", "message": "<reason>"}``
"""

import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import boto3
from bookshelf_streaming_agent import BookshelfStreamingAgent
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# In-memory session store: session_id → list[ModelMessage]
_session_history: Dict[str, List[Any]] = {}

_METADATA_FIELDS = (
    "title",
    "author",
    "isbn",
    "publisher",
    "published_year",
    "description",
    "confidence",
)


class MetadataRefineHandler:
    """Handles the full lifecycle of a metadata refinement chat request."""

    def __init__(
        self,
        agent: Optional[BookshelfStreamingAgent] = None,
    ) -> None:
        self._model_id: str = os.environ["BEDROCK_MODEL_ID"]
        region: str = os.environ.get(
            "BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
        )

        if agent is None:
            bedrock_client = boto3.client("bedrock-runtime", region_name=region)
            agent = BookshelfStreamingAgent(
                model_id=self._model_id,
                bedrock_client=bedrock_client,
                refinement=True,
            )
        self._agent = agent

    async def handle(self, request: Request) -> StreamingResponse:
        """Load history, build prompt, and return a streaming SSE response."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        session_id: Optional[str] = body.get("session_id")
        message: Optional[str] = body.get("message")
        current_metadata: dict = body.get("current_metadata", {})

        if not session_id or not message:
            raise HTTPException(status_code=400, detail="session_id and message are required")

        history = _session_history.get(session_id, [])

        metadata_str = json.dumps(current_metadata, indent=2)
        prompt = (
            f"Current metadata:\n{metadata_str}\n\n"
            f"User: {message}\n\n"
            "Update any metadata fields based on the user's feedback and respond conversationally."
        )

        return StreamingResponse(
            self._stream_events(prompt, history, session_id),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    async def _stream_events(  # pragma: no cover
        self,
        prompt: str,
        history: List[Any],
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        prev_msg = ""
        prev_fields: dict = {}
        all_messages = None

        try:
            async with self._agent.run_stream(
                prompt,
                message_history=history or None,
            ) as result:
                async for partial in result.stream_output():
                    current_msg: str = partial.assistantMessage or ""
                    if len(current_msg) > len(prev_msg):
                        yield _sse("text_delta", {"delta": current_msg[len(prev_msg) :]})
                        prev_msg = current_msg

                    for field in _METADATA_FIELDS:
                        value = getattr(partial, field, None)
                        if value != prev_fields.get(field):
                            prev_fields[field] = value
                            yield _sse("metadata_update", {"field": field, "value": value})

                all_messages = result.all_messages()

        except Exception as exc:  # pragma: no cover
            logger.exception("Agent stream error during refinement: %s", exc)
            yield _sse("error", {"message": "Agent error — please try again"})
            return

        # Persist updated message history for next turn
        if all_messages:  # pragma: no cover
            _session_history[session_id] = list(all_messages)

        yield _sse("complete", {})


def _sse(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
