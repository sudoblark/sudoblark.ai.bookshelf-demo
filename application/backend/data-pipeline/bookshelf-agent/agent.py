"""BookshelfAgent — pydantic-ai Agent for book metadata extraction.

``BookshelfAgent`` wraps a pydantic-ai ``Agent`` and injects the book metadata
system prompt so callers only need to supply a prompt string and an S3 toolset.

Tools and toolsets can be passed per-call via ``run()``, keeping agent
capabilities (e.g. S3 chunked reader) separate from Lambda logic.

Usage::

    from agent import BookshelfAgent
    from models import BookMetadata
    from s3_toolset import build_s3_chunked_reader

    agent = BookshelfAgent(model_id, bedrock_client)
    toolset = build_s3_chunked_reader(s3_client, bucket, key)
    metadata: BookMetadata = agent.run("Extract the book metadata.", toolsets=[toolset])
"""

import logging
from typing import Any, Optional

from constants import SYSTEM_PROMPT
from models import BookMetadata
from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

logger = logging.getLogger(__name__)


class BookshelfAgent:
    """pydantic-ai Agent for extracting structured book metadata from S3 files."""

    def __init__(self, model_id: str, bedrock_client: Any) -> None:
        provider = BedrockProvider(bedrock_client=bedrock_client)
        model = BedrockConverseModel(model_id, provider=provider)
        self._agent: Agent[None, BookMetadata] = Agent(
            model,
            output_type=BookMetadata,
            system_prompt=SYSTEM_PROMPT,
        )

    def run(self, prompt: str, toolsets: Optional[list] = None) -> BookMetadata:
        """Extract book metadata using the provided prompt and toolsets.

        Args:
            prompt:   User prompt describing the extraction task.
            toolsets: Optional pydantic-ai toolsets to make available for this run.

        Returns:
            Validated BookMetadata instance.
        """
        result = self._agent.run_sync(prompt, toolsets=toolsets or [])
        logger.info("Successfully extracted book metadata")
        return result.output
