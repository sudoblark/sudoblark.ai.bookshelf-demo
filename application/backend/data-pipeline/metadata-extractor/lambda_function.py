"""
Lambda function to extract book metadata from images using AWS Bedrock.

This function is triggered by S3 ObjectCreated events on the raw bucket
and uses Claude 3 Haiku via AWS Bedrock to extract book metadata from
images, then writes the results to Parquet format in the processed bucket.
"""

import os
from typing import Any, Dict

import boto3
from agent import BookshelfAgent
from common.handler import BaseDataProcessor
from common.s3 import parse_upload_key
from common.tracker import BookshelfTracker, UploadStage
from config import Config
from parquet_writer import ParquetWriter  # noqa: F401
from processor import BookshelfProcessor


class MetadataExtractorHandler(BaseDataProcessor):
    """Extracts book metadata from S3 image objects using Bedrock."""

    def __init__(
        self, s3_client: Any = None, bedrock_client: Any = None, tracker: Any = None
    ) -> None:
        super().__init__(s3_client)
        _bedrock_client = bedrock_client or boto3.client("bedrock-runtime")
        config = Config.from_env()
        agent = BookshelfAgent(config.bedrock_model_id, _bedrock_client)
        self._processor = BookshelfProcessor(agent=agent, s3_client=self.s3_client)
        if tracker is not None:
            self._tracker = tracker
        else:
            tracking_table = os.environ.get("TRACKING_TABLE", "")
            if not tracking_table:
                raise ValueError("TRACKING_TABLE environment variable is required")
            self._tracker = BookshelfTracker(table_name=tracking_table)

    def __call__(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        if "upload_id" in event and "key" in event:
            result = self.process_record(event["key"])
            return {"status": "success", "output_key": result}
        batch_response: Dict[str, Any] = super().__call__(event, context)
        return batch_response

    def process_record(self, key: str) -> str:
        user_id, upload_id, filename = parse_upload_key(key)

        self._tracker.start_stage(upload_id, UploadStage.ENRICHMENT, self.data_lake.raw, key)
        try:
            parquet_key = self._processor.process(self.data_lake.raw, self.data_lake.processed, key)
        except Exception as exc:
            self._tracker.fail_stage(user_id, upload_id, UploadStage.ENRICHMENT, str(exc))
            raise

        self._tracker.complete_stage(
            user_id,
            upload_id,
            UploadStage.ENRICHMENT,
            self.data_lake.processed,
            parquet_key,
        )
        return parquet_key


handler = MetadataExtractorHandler()
