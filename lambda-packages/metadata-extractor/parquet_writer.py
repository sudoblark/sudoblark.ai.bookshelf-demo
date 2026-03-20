import io
import logging
from datetime import datetime
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


class ParquetWriter:
    """Writes metadata to Parquet format and uploads to S3."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def write(self, metadata: Dict[str, Any], bucket: str) -> str:
        """Convert metadata to Parquet and upload to S3.

        Args:
            metadata: Metadata dictionary (must contain an 'id' key).
            bucket: Full S3 bucket name.

        Returns:
            S3 key of the uploaded Parquet file.

        Raises:
            ValueError: If metadata or bucket is empty.
            ClientError: If the S3 upload fails.
        """
        if not metadata or not bucket:
            raise ValueError("metadata and processed_bucket must not be empty")

        try:
            df = pd.DataFrame([metadata])

            now = datetime.utcnow()
            parquet_key: str = (
                f"processed/year={now.strftime('%Y')}/month={now.strftime('%m')}/"
                f"day={now.strftime('%d')}/"
                f"metadata_{now.strftime('%Y%m%d_%H%M%S')}_{metadata['id']}.parquet"
            )

            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, engine="pyarrow")
            parquet_bytes: bytes = buffer.getvalue()

            logger.info(f"Generated Parquet file: {len(parquet_bytes)} bytes")

            self._client.put_object(
                Bucket=bucket,
                Key=parquet_key,
                Body=parquet_bytes,
                ContentType="application/octet-stream",
            )

            logger.info(f"Uploaded Parquet: s3://{bucket}/{parquet_key}")
            return parquet_key

        except Exception as e:
            logger.error(f"Parquet write failed: {str(e)}", exc_info=True)
            raise
