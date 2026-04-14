"""Image extraction toolset for pydantic-ai agents.

Provides tools to:
- Base64-encode an image for inline reference in prompts
- Extract OCR text from an image via Claude's vision capabilities
- Get basic image metadata (dimensions, format, size)

Images are automatically compressed to fit within Haiku's context window.
This toolset is much more efficient than chunked S3 reading for images.
"""

import io
import json
import logging
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import FunctionToolset

logger = logging.getLogger(__name__)


class ImageMetadata(BaseModel):
    """Metadata about an image stored in S3."""

    size_bytes: int = Field(..., description="Size of the image in bytes")
    content_type: str = Field(default="image/jpeg", description="MIME type of the image")
    key: str = Field(..., description="S3 object key")


class TextractResult(BaseModel):
    """Result of OCR extraction via AWS Textract."""

    extracted_text: str = Field(..., description="All extracted text from the image")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Average OCR confidence (0-1)")
    line_count: int = Field(default=0, description="Number of high-confidence text lines")
    raw_blocks: str = Field(
        default="[]",
        description="JSON string of raw Textract blocks (LINE and WORD types)",
    )


def build_image_toolset(
    s3_client: Any, bucket: str, key: str, textract_client: Any = None
) -> FunctionToolset:
    """Return a ``FunctionToolset`` for image extraction and analysis.

    Uses AWS Textract for OCR extraction (no base64 encoding needed).
    Enforces call limits: extract_text_via_textract() can only be called once.

    Args:
        s3_client: A ``boto3`` S3 client.
        bucket: The S3 bucket name.
        key: The S3 object key.
        textract_client: Optional ``boto3`` Textract client. If not provided, one is created.

    Returns:
        A ``FunctionToolset`` exposing ``get_image_metadata`` and ``extract_text_via_textract``.
    """
    if textract_client is None:
        textract_client = io  # Will be set to actual client in handler

    toolset: FunctionToolset = FunctionToolset()
    textract_call_count = [0]  # Mutable counter in closure

    @toolset.tool_plain
    def get_image_metadata() -> ImageMetadata:  # pragma: no cover
        """Get metadata about the image: size (bytes), content-type.

        Returns:
            ImageMetadata with size_bytes, content_type, and key.
        """
        try:
            response = s3_client.head_object(Bucket=bucket, Key=key)
            return ImageMetadata(
                size_bytes=response["ContentLength"],
                content_type=response.get("ContentType", "image/jpeg"),
                key=key,
            )
        except Exception as e:  # pragma: no cover
            logger.exception("Failed to get image metadata")
            raise ValueError(f"Failed to get image metadata: {str(e)}")

    @toolset.tool_plain
    def extract_text_via_textract() -> TextractResult:  # pragma: no cover
        """Extract all visible text from the book cover using AWS Textract OCR.

        Fast, accurate OCR without needing to send base64 to the LLM.
        Focuses on: title, author, ISBN, publisher, publication year.

        NOTE: This tool can only be called ONCE per request. Subsequent calls will be rejected.

        Returns:
            TextractResult with extracted_text, confidence, and line_count.
        """
        textract_call_count[0] += 1
        if textract_call_count[0] > 1:  # pragma: no cover
            raise ValueError("extract_text_via_textract() can only be called once per request")

        try:
            # Call Textract to extract text from the S3 image
            response = textract_client.detect_document_text(
                Document={"S3Object": {"Bucket": bucket, "Name": key}}
            )

            # Extract and structure the detected text
            blocks = response.get("Blocks", [])
            lines = []

            for block in blocks:
                if block["BlockType"] == "LINE":
                    text = block.get("Text", "")
                    confidence = block.get("Confidence", 0)
                    if text and confidence > 50:  # Only include high-confidence text
                        lines.append({"text": text, "confidence": confidence})

            extracted_text = "\n".join([line["text"] for line in lines])
            avg_confidence = sum(line["confidence"] for line in lines) / len(lines) if lines else 0

            logger.info(
                f"Extracted {len(lines)} lines from book cover via Textract "
                f"(avg confidence: {avg_confidence:.1f}%)"
            )

            return TextractResult(
                extracted_text=extracted_text,
                confidence=avg_confidence / 100,  # Normalize to 0-1
                line_count=len(lines),
                raw_blocks=json.dumps(
                    [
                        {
                            "text": b.get("Text"),
                            "type": b.get("BlockType"),
                            "confidence": b.get("Confidence"),
                        }
                        for b in blocks
                        if b["BlockType"] in ("LINE", "WORD")
                    ]
                ),
            )
        except Exception as e:  # pragma: no cover
            logger.exception("Failed to extract text via Textract")
            raise ValueError(f"Failed to extract text via Textract: {str(e)}")

    return toolset
