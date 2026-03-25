"""
Lambda function to extract book metadata from images using AWS Bedrock.

This function is triggered by S3 ObjectCreated events on the raw bucket
and uses Claude 3 Haiku via AWS Bedrock to extract book metadata from
images, then writes the results to Parquet format in the processed bucket.
"""

from typing import Any

import boto3
from bedrock_extractor import BedrockMetadataExtractor  # noqa: F401
from common.handler import BaseS3BatchHandler
from config import Config
from image_processor import ImageProcessor  # noqa: F401
from parquet_writer import ParquetWriter  # noqa: F401
from processor import BookshelfProcessor


class MetadataExtractorHandler(BaseS3BatchHandler):
    """Extracts book metadata from S3 image objects using Bedrock."""

    def __init__(self, s3_client: Any = None, bedrock_client: Any = None) -> None:
        super().__init__(s3_client)
        _bedrock_client = bedrock_client or boto3.client("bedrock-runtime")
        config = Config.from_env()
        self._processor = BookshelfProcessor(
            config=config,
            s3_client=self.s3_client,
            bedrock_client=_bedrock_client,
        )

    def process_record(self, bucket: str, key: str) -> str:
        return self._processor.process(bucket, key)


handler = MetadataExtractorHandler()
