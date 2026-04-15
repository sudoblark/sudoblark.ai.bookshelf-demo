"""Async streaming variant of BookshelfAgent.

Unlike the synchronous ``BookshelfAgent`` in the bookshelf-agent layer (which
uses ``run_sync``), this module exposes ``run_stream()`` so FastAPI handlers
can yield partial ``StreamingBookMetadataResponse`` objects as SSE events.

The bookshelf-agent layer is mounted at ``/opt/bookshelf-agent`` inside the
container and added to ``PYTHONPATH`` via docker-compose, so ``constants`` and
``s3_toolset`` are importable at runtime without copying.

Usage::

    agent = BookshelfStreamingAgent(model_id=model_id, bedrock_client=client)

    async with agent.run_stream(prompt, toolsets=[toolset]) as result:
        async for partial in result.stream_output():
            delta = partial.assistantMessage[len(prev):]
            ...
        final: StreamingBookMetadataResponse = result.output
"""

import logging
from typing import Any, Optional

from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider
from streaming_models import StreamingBookMetadataResponse

logger = logging.getLogger(__name__)

# INITIAL EXTRACTION: Categorize pre-extracted OCR and ISBN lookup data
# Backend has already done: OCR extraction, ISBN regex matching, and ISBN metadata lookup
# Agent's job: categorize the data and return structured metadata with confidence
INITIAL_SYSTEM_PROMPT = """\
Categorize book metadata based on provided OCR text and ISBN lookup results.

Return JSON with: title, author, isbn, publisher, published_year, description, confidence (0.0-1.0).

Use exact values from the provided context. For missing fields, use null.
Confidence reflects how confident you are in the accuracy of the extracted metadata.
"""

# REFINEMENT: Help user refine initial metadata through conversation
# Agent's job: accept user corrections, update fields, acknowledge changes, maintain all fields
REFINEMENT_SYSTEM_PROMPT = """\
You are a helpful metadata assistant. The user is refining book metadata from an initial extraction.

When user suggests changes, update relevant fields and acknowledge briefly (1-2 sentences).
Always return ALL metadata fields in structured output, carrying forward previously confirmed values.
User will click "Save book" when done—do not prompt them to save.

For confidence: keep the backend's initial value unless user provides new information that
changes certainty.
"""


class BookshelfStreamingAgent:
    """pydantic-ai Agent that streams ``StreamingBookMetadataResponse`` output.

    Instantiate once per handler; ``run_stream`` is called per request.
    """

    def __init__(self, model_id: str, bedrock_client: Any, refinement: bool = False) -> None:
        provider = BedrockProvider(bedrock_client=bedrock_client)
        model = BedrockConverseModel(model_id, provider=provider)
        system_prompt = REFINEMENT_SYSTEM_PROMPT if refinement else INITIAL_SYSTEM_PROMPT
        self._agent: Agent[None, StreamingBookMetadataResponse] = Agent(
            model,
            output_type=StreamingBookMetadataResponse,
            system_prompt=system_prompt,
        )

    def run_stream(
        self,
        prompt: str,
        toolsets: Optional[list] = None,
        message_history: Optional[list] = None,
    ) -> Any:
        """Return an async context manager for streaming ``StreamingBookMetadataResponse``.

        Usage::

            async with agent.run_stream(prompt, toolsets=[toolset]) as result:
                async for partial in result.stream_output():
                    delta = partial.assistantMessage[len(prev):]
                    prev = partial.assistantMessage
                    yield _sse("text_delta", {"delta": delta})
        """
        return self._agent.run_stream(
            prompt,
            toolsets=toolsets or [],
            message_history=message_history or None,
        )
