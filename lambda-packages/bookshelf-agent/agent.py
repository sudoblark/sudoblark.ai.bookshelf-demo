"""BookshelfAgent — pydantic-ai Agent for book metadata extraction.

``BookshelfAgent`` wraps a pydantic-ai ``Agent`` and injects the book metadata
system prompt so callers only need to supply raw image bytes.

Tools and toolsets can be passed per-call via ``run()``, keeping agent
capabilities (e.g. ISBN lookup, publisher search) separate from Lambda logic.

Usage::

    from agent import BookshelfAgent
    from models import BookMetadata

    agent = BookshelfAgent(model_id, bedrock_client)
    metadata: BookMetadata = agent.run(image_bytes)
"""

import logging
from typing import Any, Optional

from constants import SYSTEM_PROMPT
from image_processor import ImageProcessor
from models import BookMetadata
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

logger = logging.getLogger(__name__)


class BookshelfAgent:
    """pydantic-ai Agent for extracting structured book metadata from cover images."""

    def __init__(self, model_id: str, bedrock_client: Any) -> None:
        provider = BedrockProvider(bedrock_client=bedrock_client)
        model = BedrockConverseModel(model_id, provider=provider)
        self._agent: Agent[None, BookMetadata] = Agent(
            model,
            output_type=BookMetadata,
            system_prompt=SYSTEM_PROMPT,
        )

    def run(self, image_bytes: bytes, toolsets: Optional[list] = None) -> BookMetadata:
        """Extract book metadata from image bytes.

        Args:
            image_bytes: Raw image bytes.
            toolsets:    Optional pydantic-ai toolsets to make available for this run.

        Returns:
            Validated BookMetadata instance.

        Raises:
            ValueError: If image_bytes is empty.
        """
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        resized = ImageProcessor.resize_to_jpeg(image_bytes)
        result = self._agent.run_sync(
            [
                "Extract the book metadata from this cover image.",
                BinaryContent(data=resized, media_type="image/jpeg"),
            ],
            toolsets=toolsets or [],
        )
        logger.info("Successfully extracted book metadata")
        return result.output
