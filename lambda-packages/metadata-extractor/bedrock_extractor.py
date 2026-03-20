import base64
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, cast

from botocore.exceptions import BotoCoreError, ClientError
from constants import SYSTEM_PROMPT
from image_processor import ImageProcessor
from models import BookMetadata

logger = logging.getLogger(__name__)


class BedrockMetadataExtractor:
    """Extracts book metadata from images using AWS Bedrock."""

    def __init__(self, model_id: str, client: Any) -> None:
        self._model_id = model_id
        self._client = client

    def extract(self, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract book metadata from image bytes.

        Args:
            image_bytes: Raw image bytes.
            filename: Original filename, used to populate metadata defaults.

        Returns:
            Dictionary with validated metadata fields.

        Raises:
            ValueError: If image_bytes is empty or Bedrock returns no content.
            ClientError: If the Bedrock API call fails.
        """
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        try:
            resized: bytes = ImageProcessor.resize_to_jpeg(image_bytes)
            image_base64: str = base64.b64encode(resized).decode("utf-8")

            request_body: Dict[str, Any] = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": SYSTEM_PROMPT},
                        ],
                    }
                ],
            }

            logger.debug(f"Calling Bedrock with model: {self._model_id}")

            response = self._client.invoke_model(
                modelId=self._model_id, body=json.dumps(request_body)
            )
            response_body: Dict[str, Any] = json.loads(response["body"].read())

            if "content" not in response_body or not response_body["content"]:
                raise ValueError("Bedrock response missing content")

            response_text: str = response_body["content"][0]["text"]
            logger.debug(f"Bedrock response: {response_text}")

            metadata: Dict[str, Any] = self._parse_response(response_text)
            metadata = self._apply_defaults(metadata, filename)

            logger.info(f"Successfully extracted metadata for: {filename}")
            return metadata

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Bedrock API error: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}", exc_info=True)
            raise

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Bedrock response text into a validated metadata dictionary."""
        try:
            parsed: Dict[str, Any] = json.loads(response_text.strip())
            validated: BookMetadata = BookMetadata(**parsed)
            logger.debug(f"Successfully validated JSON response: {validated}")
            return cast(Dict[str, Any], validated.model_dump())  # type: ignore[redundant-cast]

        except json.JSONDecodeError:
            logger.warning("Response was not valid JSON, attempting to extract from text")
            logger.debug(f"Response text: {response_text}")

            try:
                start: int = response_text.find("{")
                end: int = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed_fallback: Dict[str, Any] = json.loads(response_text[start:end])
                    validated_fallback: BookMetadata = BookMetadata(**parsed_fallback)
                    logger.debug(f"Extracted and validated JSON from text: {validated_fallback}")
                    return cast(Dict[str, Any], validated_fallback.model_dump())  # type: ignore[redundant-cast]
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not extract JSON from response: {e}")

        except Exception as e:
            logger.warning(f"Pydantic validation failed: {e}")

        logger.warning("Using default metadata due to parsing failures")
        return cast(Dict[str, Any], BookMetadata().model_dump())  # type: ignore[redundant-cast]

    @staticmethod
    def _apply_defaults(metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Apply required default fields to metadata if absent."""
        if not metadata.get("id"):
            metadata["id"] = str(uuid.uuid4())
        if not metadata.get("filename"):
            metadata["filename"] = filename
        if not metadata.get("processed_at"):
            metadata["processed_at"] = datetime.utcnow().isoformat() + "Z"
        return metadata
