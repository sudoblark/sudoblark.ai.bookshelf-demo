"""Ingestion-tracking DynamoDB helper for the bookshelf demo pipeline.

``BookshelfTracker``
    Provides a consistent API for all pipeline components to maintain an
    audit trail of each file's progress through the pipeline in the DynamoDB
    ingestion-tracking table.

    Schema
    ------
    Each record has the following top-level fields:

    upload_id   : str  — partition key, UUID
    user_id     : str
    stage       : str  — name of the last completed stage (e.g. "analysed",
                         "embedding") or "failed" when a stage fails
    stages      : dict — keyed by stage name; each value contains:
                         startedAt, endedAt, sourceBucket, sourceKey,
                         destinationBucket (optional), destinationKey (optional),
                         error (optional)
    created_at  : str  — ISO-8601 timestamp
    updated_at  : str  — ISO-8601 timestamp

    Methods:
        create_record  — call when a file first lands in S3
        start_stage    — call at the start of a processing stage
        complete_stage — call on successful stage completion
        fail_stage     — call on stage failure

Usage::

    from common.tracker import BookshelfTracker, UploadStage

    tracker = BookshelfTracker(
        dynamodb_resource=boto3.resource("dynamodb"),
        table_name=os.environ["TRACKING_TABLE"],
    )

    tracker.create_record(user_id, upload_id)
    tracker.start_stage(upload_id, UploadStage.ANALYSED, bucket, key)
    tracker.complete_stage(user_id, upload_id, UploadStage.ANALYSED, dest_bucket, dest_key)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3


class UploadStage(str, Enum):
    """Ordered pipeline stages for a single file upload."""

    USER_UPLOAD = "user_upload"
    ROUTING = "routing"
    AV_SCAN = "av_scan"
    ANALYSED = "analysed"
    PROCESSED = "processed"
    EMBEDDING = "embedding"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BookshelfTracker:
    """DynamoDB ingestion-tracking helper.

    Args:
        dynamodb_resource: boto3 DynamoDB resource. Pass a mock in tests.
        table_name: Name of the ingestion-tracking DynamoDB table.
    """

    def __init__(self, dynamodb_resource: Any = None, table_name: str = "") -> None:
        self._resource = dynamodb_resource or boto3.resource("dynamodb")
        self._table = self._resource.Table(table_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_record(
        self,
        user_id: str,
        upload_id: str,
    ) -> None:
        """Create a new tracking record when a file first lands in S3.

        Args:
            user_id: Cognito user sub.
            upload_id: UUID identifying this upload batch (partition key).
        """
        now = _now_iso()
        self._table.put_item(
            Item={
                "upload_id": upload_id,
                "user_id": user_id,
                "stage": "queued",
                "stages": {},
                "created_at": now,
                "updated_at": now,
            }
        )

    def start_stage(
        self,
        upload_id: str,
        stage: UploadStage,
        source_bucket: str,
        source_key: str,
    ) -> None:
        """Record the start of a processing stage.

        Args:
            upload_id: UUID identifying this upload batch (partition key).
            stage: The pipeline stage beginning.
            source_bucket: Bucket the file is being read from.
            source_key: Key the file is being read from.
        """
        now = _now_iso()
        # Only include non-None values; DynamoDB doesn't store null in maps
        stage_entry = {
            "startedAt": now,
            "sourceBucket": source_bucket,
            "sourceKey": source_key,
        }
        self._table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression=("SET #stages.#stage_name = :entry, updated_at = :now"),
            ExpressionAttributeNames={
                "#stages": "stages",
                "#stage_name": stage.value,
            },
            ExpressionAttributeValues={
                ":entry": stage_entry,
                ":now": now,
            },
        )

    def complete_stage(
        self,
        user_id: str,
        upload_id: str,
        stage: UploadStage,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Mark a stage as successfully completed.

        Args:
            user_id: Cognito user sub.
            upload_id: UUID identifying this upload batch (partition key).
            stage: The pipeline stage completing successfully.
            dest_bucket: Bucket the file was written to.
            dest_key: Key the file was written to.
        """
        import logging

        logger = logging.getLogger(__name__)

        now = _now_iso()
        # Read existing stage data to preserve all fields
        record = self._table.get_item(Key={"upload_id": upload_id}).get("Item", {})
        existing = (record.get("stages") or {}).get(stage.value) or {}

        logger.debug(
            f"complete_stage: upload_id={upload_id}, stage={stage.value}, "
            f"existing_keys={list(existing.keys())}"
        )

        # Build complete entry, preserving all existing fields and adding completion data
        completed_entry = dict(existing)  # Copy all existing fields
        completed_entry["endedAt"] = now
        completed_entry["destinationBucket"] = dest_bucket
        completed_entry["destinationKey"] = dest_key

        self._table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression="SET #stages.#stage_name = :entry, #stage = :stage_name, updated_at = :now",
            ExpressionAttributeNames={
                "#stages": "stages",
                "#stage_name": stage.value,
                "#stage": "stage",
            },
            ExpressionAttributeValues={
                ":entry": completed_entry,
                ":stage_name": stage.value,
                ":now": now,
            },
        )

    def fail_stage(
        self,
        user_id: str,
        upload_id: str,
        stage: UploadStage,
        error_message: str,
    ) -> None:
        """Mark a stage as failed.

        Args:
            user_id: Cognito user sub.
            upload_id: UUID identifying this upload batch (partition key).
            stage: The pipeline stage that failed.
            error_message: Human-readable failure reason.
        """
        now = _now_iso()
        # Read existing stage data to preserve all fields
        record = self._table.get_item(Key={"upload_id": upload_id}).get("Item", {})
        existing = (record.get("stages") or {}).get(stage.value) or {}

        # Build complete entry, preserving existing fields and adding error
        failed_entry = dict(existing)  # Copy all existing fields
        failed_entry["endedAt"] = now
        failed_entry["error"] = error_message

        self._table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression="SET #stages.#stage_name = :entry, #stage = :failed, updated_at = :now",
            ExpressionAttributeNames={
                "#stages": "stages",
                "#stage_name": stage.value,
                "#stage": "stage",
            },
            ExpressionAttributeValues={
                ":entry": failed_entry,
                ":failed": "failed",
                ":now": now,
            },
        )

    def list_all(self, limit: int = 100) -> List[dict]:
        """Scan all tracking records (ops dashboard use only).

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of tracking record dicts.
        """
        response = self._table.scan(Limit=limit)
        items: List[Dict[Any, Any]] = response.get("Items", [])
        return items

    def get_by_id(self, upload_id: str) -> Optional[dict]:
        """Return a single tracking record by upload_id, or None if not found.

        Args:
            upload_id: UUID identifying the upload batch (partition key).

        Returns:
            Tracking record dict, or None if no record exists.
        """
        response = self._table.get_item(Key={"upload_id": upload_id})
        item: Optional[Dict[Any, Any]] = response.get("Item")
        return item
