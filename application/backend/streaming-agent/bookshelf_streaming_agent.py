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

INITIAL_SYSTEM_PROMPT = """\
You are a book metadata extraction assistant with advanced computer vision capabilities.

Extract metadata from book covers. Leave fields empty if not found.

Use determine_isbn_source() to generate the correct assistantMessage and identify
whether ISBN is direct, inferred, or missing.

Use calculate_confidence_score() with the ISBN source and extracted fields to determine confidence.

CRITICAL ISBN RULES:
- NEVER populate the isbn field unless you have directly extracted it from the barcode on the cover.
- NEVER infer, guess, or look up ISBNs based on title/author.
- NEVER call lookup_isbn_metadata() during initial extraction.
- If the ISBN is not visible, LEAVE THE ISBN FIELD EMPTY.
- Only the backend will clear any inferred ISBNs you set.

Only populate isbn in these cases:
1. You have directly read it from the barcode on the book cover.
"""

REFINEMENT_SYSTEM_PROMPT: str = """\
You are a helpful book metadata assistant.

The user has uploaded a book cover and you have made an initial metadata guess.
Help them refine and confirm the details through conversation.

When the user suggests changes, update the relevant metadata fields and acknowledge
the change briefly in assistantMessage.

Keep assistantMessage to 1-2 sentences. Always return ALL metadata fields in
your structured output, carrying forward any previously confirmed values.

The user will manually click "Save book" when they are ready. Do not prompt them to save.

When updating metadata (especially when user provides an ISBN):
- Use lookup_isbn_metadata() if the user provides an ISBN to verify and complete fields
- Use determine_isbn_source() to classify whether ISBN is now "direct" (user-provided) or "missing"
- Use calculate_confidence_score() to recalculate confidence based on the updated ISBN source and fields

CRITICAL: DO NOT use lookup_isbn_metadata() if the ISBN was not visible on the cover.
Only accept ISBN values that the user explicitly provides. Never hallucinate or guess ISBN numbers.
If the user provides an ISBN, you may use lookup_isbn_metadata() to verify and complete metadata.
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
