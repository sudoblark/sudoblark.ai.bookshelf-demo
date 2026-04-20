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

import logging
import os
from typing import Any, Dict, Optional

import boto3
from common.tracker import BookshelfTracker, UploadStage

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _get_clients() -> tuple:
    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")
    return s3, dynamodb


def _find_raw_key(record: dict) -> Optional[str]:
    """Return the S3 key from the completed ANALYSED stage."""
    stages = record.get("stages") or {}
    analysed = stages.get(UploadStage.ANALYSED.value) or {}
    return analysed.get("destinationKey")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Step Functions entry point.

    Args:
        event: Must contain ``upload_id`` (str).
        context: Lambda context (unused).

    Returns:
        Dict with ``upload_id`` and ``processed_key`` on success.

    Raises:
        ValueError: If upload_id is missing, no tracking record found, or no ANALYSED stage.
    """
    upload_id: str = event.get("upload_id", "")
    if not upload_id:
        raise ValueError("upload_id is required in event payload")

    raw_bucket: str = os.environ["RAW_BUCKET"]
    processed_bucket: str = os.environ["PROCESSED_BUCKET"]
    tracking_table: str = os.environ["TRACKING_TABLE"]

    s3, dynamodb = _get_clients()
    tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=tracking_table)

    record = tracker.get_by_id(upload_id)
    if not record:
        raise ValueError(f"No tracking record found for upload_id={upload_id}")

    raw_key = _find_raw_key(record)
    if not raw_key:
        raise ValueError(f"No completed ANALYSED stage found for upload_id={upload_id}")

    tracker.start_stage(
        upload_id=upload_id,
        stage=UploadStage.PROCESSED,
        source_bucket=raw_bucket,
        source_key=raw_key,
    )

    # Copy metadata JSON from raw to processed at the same key path
    response = s3.get_object(Bucket=raw_bucket, Key=raw_key)
    body = response["Body"].read()

    s3.put_object(
        Bucket=processed_bucket,
        Key=raw_key,
        Body=body,
        ContentType="application/json",
    )
    logger.info(
        "Copied metadata s3://%s/%s → s3://%s/%s", raw_bucket, raw_key, processed_bucket, raw_key
    )

    tracker.complete_stage(
        user_id="system",
        upload_id=upload_id,
        stage=UploadStage.PROCESSED,
        dest_bucket=processed_bucket,
        dest_key=raw_key,
    )

    return {"upload_id": upload_id, "processed_key": raw_key}
