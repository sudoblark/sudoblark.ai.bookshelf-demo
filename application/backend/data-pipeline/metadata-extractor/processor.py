import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from agent import BookshelfAgent
from botocore.exceptions import ClientError
from parquet_writer import ParquetWriter
from s3_toolset import build_s3_chunked_reader

logger = logging.getLogger(__name__)


class BookshelfProcessor:
    """Orchestrates metadata extraction from S3 and Parquet persistence."""

    def __init__(self, agent: BookshelfAgent, s3_client: Any) -> None:
        self._agent = agent
        self._s3_client = s3_client
        self._writer = ParquetWriter(s3_client)

    def process(self, source_bucket: str, processed_bucket: str, image_key: str) -> str:
        """Extract book metadata from an S3 file and write to Parquet.

        Args:
            source_bucket: S3 bucket containing the file (raw tier).
            processed_bucket: S3 bucket for Parquet output (processed tier).
            image_key: S3 key of the file.

        Returns:
            S3 key of the uploaded Parquet file.

        Raises:
            ValueError: If any input is empty.
            ClientError: If S3 operations fail.
        """
        if not source_bucket or not image_key:
            raise ValueError("source_bucket and image_key must not be empty")

        logger.info(f"Extracting metadata from s3://{source_bucket}/{image_key}")

        try:
            toolset = build_s3_chunked_reader(self._s3_client, source_bucket, image_key)
            book_metadata = self._agent.run(
                "Extract the book metadata from the S3 file.", toolsets=[toolset]
            )
            metadata = self._apply_defaults(book_metadata.model_dump(), image_key)
            logger.info(f"Extracted metadata: {metadata.get('title', 'Unknown')}")

            parquet_key: str = self._writer.write(metadata, processed_bucket)
            logger.info(f"Uploaded Parquet file: s3://{processed_bucket}/{parquet_key}")
            return parquet_key

        except ClientError as e:
            error_code: str = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 operation failed: {error_code}", exc_info=True)
            raise

    @staticmethod
    def _apply_defaults(metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Stamp operational metadata fields if the model did not populate them."""
        if not metadata.get("id"):
            metadata["id"] = str(uuid.uuid4())
        if not metadata.get("filename"):
            metadata["filename"] = filename
        if not metadata.get("processed_at"):
            metadata["processed_at"] = datetime.utcnow().isoformat() + "Z"
        return metadata
