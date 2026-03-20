import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from constants import SYSTEM_PROMPT
from image_processor import ImageProcessor
from models import BookMetadata
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

logger = logging.getLogger(__name__)


class BedrockMetadataExtractor:
    """Extracts book metadata from images using pydantic-ai with BedrockConverseModel."""

    def __init__(self, model_id: str, client: Any) -> None:
        self._model_id = model_id
        provider = BedrockProvider(bedrock_client=client)
        model = BedrockConverseModel(model_id, provider=provider)
        self._agent: Agent[None, BookMetadata] = Agent(
            model,
            output_type=BookMetadata,
            system_prompt=SYSTEM_PROMPT,
        )

    def extract(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract book metadata from image bytes.

        Args:
            image_bytes: Raw image bytes.
            filename: Original filename, used to populate metadata defaults.

        Returns:
            Dictionary with validated metadata fields including id, filename,
            and processed_at.

        Raises:
            ValueError: If image_bytes is empty.
        """
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        resized: bytes = ImageProcessor.resize_to_jpeg(image_bytes)
        result = self._agent.run_sync(
            [
                "Extract the book metadata from this cover image.",
                BinaryContent(data=resized, media_type="image/jpeg"),
            ]
        )

        logger.info(f"Successfully extracted metadata for: {filename}")
        metadata: Dict[str, Any] = result.output.model_dump()
        return self._apply_defaults(metadata, filename)

    @staticmethod
    def _apply_defaults(metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Apply required operational fields to metadata if absent."""
        if not metadata.get("id"):
            metadata["id"] = str(uuid.uuid4())
        if not metadata.get("filename"):
            metadata["filename"] = filename
        if not metadata.get("processed_at"):
            metadata["processed_at"] = datetime.utcnow().isoformat() + "Z"
        return metadata
