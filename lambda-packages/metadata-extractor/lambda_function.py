"""
Lambda function to extract book metadata from images using AWS Bedrock.

This function is triggered by S3 ObjectCreated events on the raw bucket
and uses Claude 3 Haiku via AWS Bedrock to extract book metadata from
images, then writes the results to Parquet format in the processed bucket.
"""

import os
from typing import Any

import boto3
from bedrock_extractor import BedrockMetadataExtractor  # noqa: F401
from common.handler import BaseS3BatchHandler
from common.s3 import parse_upload_key, resolve_bucket
from common.tracker import BookshelfTracker, UploadStage
from config import Config
from image_processor import ImageProcessor  # noqa: F401
from parquet_writer import ParquetWriter  # noqa: F401
from processor import BookshelfProcessor


class MetadataExtractorHandler(BaseS3BatchHandler):
    """Extracts book metadata from S3 image objects using Bedrock."""

    def __init__(
        self, s3_client: Any = None, bedrock_client: Any = None, tracker: Any = None
    ) -> None:
        super().__init__(s3_client)
        _bedrock_client = bedrock_client or boto3.client("bedrock-runtime")
        config = Config.from_env()
        self._processor = BookshelfProcessor(
            config=config,
            s3_client=self.s3_client,
            bedrock_client=_bedrock_client,
        )
        if tracker is not None:
            self._tracker = tracker
        else:
            tracking_table = os.environ.get("TRACKING_TABLE", "")
            if not tracking_table:
                raise ValueError("TRACKING_TABLE environment variable is required")
            self._tracker = BookshelfTracker(table_name=tracking_table)

    def process_record(self, bucket: str, key: str) -> str:
        user_id, upload_id, filename = parse_upload_key(key)
        processed_bucket = resolve_bucket(bucket, self._processor._config.processed_bucket)

        self._tracker.start_stage(user_id, upload_id, filename, UploadStage.ENRICHMENT, bucket, key)
        try:
            parquet_key = self._processor.process(bucket, key)
        except Exception as exc:
            self._tracker.fail_stage(user_id, upload_id, filename, UploadStage.ENRICHMENT, str(exc))
            raise

        self._tracker.complete_stage(
            user_id, upload_id, filename, UploadStage.ENRICHMENT, processed_bucket, parquet_key
        )
        return parquet_key


handler = MetadataExtractorHandler()
