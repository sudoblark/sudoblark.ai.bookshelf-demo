"""Lambda handler for copying accepted metadata from raw to processed bucket.

Invoked by the enrichment Step Functions state machine with:
    {"upload_id": "<uuid>"}

Steps
-----
1. Read the tracking record to find the ANALYSED stage destination S3 key (raw bucket).
2. Copy the metadata JSON from raw to the processed bucket at the same Hive-partitioned key.
3. Record a PROCESSED stage entry in the tracking table (start + complete).

The handler is idempotent — re-running for the same upload_id will overwrite
the existing processed file.

Environment variables
---------------------
RAW_BUCKET       S3 bucket holding accepted metadata JSON files.
PROCESSED_BUCKET S3 bucket for canonical processed metadata.
TRACKING_TABLE   DynamoDB table name for the ingestion tracker.
LOG_LEVEL        Python log level (default: INFO).
"""

import os
from typing import Any, Dict, Optional, cast

import boto3
from common.handler import BaseStepFunctionsProcessor
from common.tracker import UploadStage


class RawToProcessedCopyProcessor(BaseStepFunctionsProcessor):
    def __init__(self, s3_client=None, dynamodb_resource=None):
        super().__init__(s3_client=s3_client, dynamodb_resource=dynamodb_resource)
        self._raw_bucket: str = os.environ["RAW_BUCKET"]
        self._processed_bucket: str = os.environ["PROCESSED_BUCKET"]

    def _find_raw_key(self, record: dict) -> Optional[str]:
        stages = record.get("stages") or {}
        analysed = stages.get(UploadStage.ANALYSED.value) or {}
        return analysed.get("destinationKey")

    def process(self, upload_id: str, record: dict) -> Dict[str, Any]:
        raw_key = self._find_raw_key(record)
        if not raw_key:
            raise ValueError(f"No completed ANALYSED stage found for upload_id={upload_id}")

        self.tracker.start_stage(
            upload_id=upload_id,
            stage=UploadStage.PROCESSED,
            source_bucket=self._raw_bucket,
            source_key=raw_key,
        )

        response = self.s3_client.get_object(Bucket=self._raw_bucket, Key=raw_key)
        body = response["Body"].read()

        self.s3_client.put_object(
            Bucket=self._processed_bucket,
            Key=raw_key,
            Body=body,
            ContentType="application/json",
        )
        self.logger.info(
            "Copied metadata s3://%s/%s → s3://%s/%s",
            self._raw_bucket,
            raw_key,
            self._processed_bucket,
            raw_key,
        )

        self.tracker.complete_stage(
            user_id="system",
            upload_id=upload_id,
            stage=UploadStage.PROCESSED,
            dest_bucket=self._processed_bucket,
            dest_key=raw_key,
        )

        return {"upload_id": upload_id, "processed_key": raw_key}


_processor = RawToProcessedCopyProcessor(
    s3_client=boto3.client("s3"),
    dynamodb_resource=boto3.resource("dynamodb"),
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return cast(Dict[str, Any], _processor(event, context))
