import logging
from typing import TYPE_CHECKING, Any, Dict

from bedrock_extractor import BedrockMetadataExtractor
from botocore.exceptions import ClientError
from common.s3 import resolve_bucket
from config import Config
from parquet_writer import ParquetWriter

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef

logger = logging.getLogger(__name__)


class BookshelfProcessor:
    """Orchestrates image download, metadata extraction, and Parquet persistence."""

    def __init__(self, config: Config, s3_client: Any, bedrock_client: Any) -> None:
        self._config = config
        self._s3_client = s3_client
        self._extractor = BedrockMetadataExtractor(config.bedrock_model_id, bedrock_client)
        self._writer = ParquetWriter(s3_client)

    def process(self, source_bucket: str, image_key: str) -> str:
        """Download an image from S3, extract its metadata, and write to Parquet.

        Args:
            source_bucket: Source S3 bucket containing the image.
            image_key: S3 key of the image file.

        Returns:
            S3 key of the uploaded Parquet file.

        Raises:
            ValueError: If inputs are empty or the bucket name format is invalid.
            ClientError: If S3 operations fail.
        """
        if not source_bucket or not image_key:
            raise ValueError("source_bucket and image_key must not be empty")

        processed_bucket: str = resolve_bucket(source_bucket, self._config.processed_bucket)
        logger.info(f"Extracting metadata from s3://{source_bucket}/{image_key}")

        try:
            image_obj: "GetObjectOutputTypeDef" = self._s3_client.get_object(
                Bucket=source_bucket, Key=image_key
            )
            image_bytes: bytes = image_obj["Body"].read()
            logger.info(f"Downloaded image: {len(image_bytes)} bytes")

            metadata: Dict[str, Any] = self._extractor.extract(image_bytes, image_key)
            logger.info(f"Extracted metadata: {metadata.get('title', 'Unknown')}")

            parquet_key: str = self._writer.write(metadata, processed_bucket)
            logger.info(f"Uploaded Parquet file: s3://{processed_bucket}/{parquet_key}")
            return parquet_key

        except ClientError as e:
            error_code: str = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 operation failed: {error_code}", exc_info=True)
            raise
