"""Ingestion-tracking DynamoDB helper for the bookshelf demo pipeline.

``BookshelfTracker``
    Provides a consistent API for all pipeline Lambdas to maintain an ordered
    audit trail of each file's progress through the pipeline in the DynamoDB
    ingestion-tracking table.

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

    tracker.create_record(user_id, upload_id, filename, bucket, key)
    tracker.start_stage(user_id, upload_id, filename, UploadStage.ROUTING, bucket, key)
    tracker.complete_stage(user_id, upload_id, filename, UploadStage.ROUTING, dest_bucket, dest_key)
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import boto3


class UploadStage(str, Enum):
    """Ordered pipeline stages for a single file upload.

    Extend this enum as new pipeline stages are added.
    """

    USER_UPLOAD = "user_upload"
    ROUTING = "routing"
    ENRICHMENT = "enrichment"


class StageStatus(str, Enum):
    """Status of a single pipeline stage entry."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class UploadStatus(str, Enum):
    """Top-level upload status, denormalised for cheap GSI queries."""

    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


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
        filename: str,
        source_bucket: str,
        source_key: str,
    ) -> None:
        """Create a new tracking record when a file first lands in S3.

        Args:
            user_id: Cognito user sub (partition key).
            upload_id: UUID identifying this upload batch.
            filename: Original filename.
            source_bucket: Landing bucket name.
            source_key: Full S3 key in the landing bucket.
        """
        now = _now_iso()
        self._table.put_item(
            Item={
                "user_id": user_id,
                "file_id": f"{upload_id}#{filename}",
                "upload_id": upload_id,
                "filename": filename,
                "current_status": UploadStatus.QUEUED.value,
                "stage_progress": [],
                "created_at": now,
                "updated_at": now,
            }
        )

    def start_stage(
        self,
        user_id: str,
        upload_id: str,
        filename: str,
        stage: UploadStage,
        source_bucket: str,
        source_key: str,
    ) -> None:
        """Append an in-progress stage entry and mark the upload as IN_PROGRESS.

        Uses DynamoDB ``list_append`` so no prior read is required.

        Args:
            user_id: Cognito user sub (partition key).
            upload_id: UUID identifying this upload batch.
            filename: Original filename.
            stage: The pipeline stage beginning.
            source_bucket: Bucket the file is being read from.
            source_key: Key the file is being read from.
        """
        stage_entry = {
            "stage_name": stage.value,
            "status": StageStatus.IN_PROGRESS.value,
            "start_time": _now_iso(),
            "end_time": None,
            "processing_time": None,
            "source": {"bucket": source_bucket, "key": source_key},
            "destination": None,
            "error_message": None,
        }
        self._table.update_item(
            Key={"user_id": user_id, "file_id": f"{upload_id}#{filename}"},
            UpdateExpression=(
                "SET stage_progress = list_append("
                "if_not_exists(stage_progress, :empty), :entry"
                "), current_status = :status, updated_at = :now"
            ),
            ExpressionAttributeValues={
                ":empty": [],
                ":entry": [stage_entry],
                ":status": UploadStatus.IN_PROGRESS.value,
                ":now": _now_iso(),
            },
        )

    def complete_stage(
        self,
        user_id: str,
        upload_id: str,
        filename: str,
        stage: UploadStage,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Mark the most recent in-progress entry for this stage as succeeded.

        Args:
            user_id: Cognito user sub (partition key).
            upload_id: UUID identifying this upload batch.
            filename: Original filename.
            stage: The pipeline stage completing successfully.
            dest_bucket: Bucket the file was written to.
            dest_key: Key the file was written to.
        """
        self._update_stage(
            user_id=user_id,
            upload_id=upload_id,
            filename=filename,
            stage=stage,
            status=StageStatus.SUCCESS,
            dest_bucket=dest_bucket,
            dest_key=dest_key,
            error_message=None,
            upload_status=UploadStatus.SUCCESS,
        )

    def fail_stage(
        self,
        user_id: str,
        upload_id: str,
        filename: str,
        stage: UploadStage,
        error_message: str,
    ) -> None:
        """Mark the most recent in-progress entry for this stage as failed.

        Args:
            user_id: Cognito user sub (partition key).
            upload_id: UUID identifying this upload batch.
            filename: Original filename.
            stage: The pipeline stage that failed.
            error_message: Human-readable failure reason.
        """
        self._update_stage(
            user_id=user_id,
            upload_id=upload_id,
            filename=filename,
            stage=stage,
            status=StageStatus.FAILED,
            dest_bucket=None,
            dest_key=None,
            error_message=error_message,
            upload_status=UploadStatus.FAILED,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_stage_index(self, stage_progress: list, stage: UploadStage) -> int:
        """Return the index of the most recent in-progress entry for *stage*.

        Raises:
            ValueError: if no in-progress entry for the stage exists.
        """
        for idx in reversed(range(len(stage_progress))):
            entry = stage_progress[idx]
            if (
                entry.get("stage_name") == stage.value
                and entry.get("status") == StageStatus.IN_PROGRESS.value
            ):
                return idx
        raise ValueError(f"No in-progress entry found for stage '{stage.value}'")

    def _update_stage(
        self,
        user_id: str,
        upload_id: str,
        filename: str,
        stage: UploadStage,
        status: StageStatus,
        dest_bucket: Optional[str],
        dest_key: Optional[str],
        error_message: Optional[str],
        upload_status: UploadStatus,
    ) -> None:
        key = {"user_id": user_id, "file_id": f"{upload_id}#{filename}"}
        item = self._table.get_item(Key=key).get("Item", {})
        stage_progress = list(item.get("stage_progress", []))
        idx = self._find_stage_index(stage_progress, stage)
        entry = dict(stage_progress[idx])

        end_time = _now_iso()
        try:
            start = datetime.fromisoformat(entry["start_time"])
            end = datetime.fromisoformat(end_time)
            processing_time = Decimal(str(round((end - start).total_seconds(), 3)))
        except (KeyError, ValueError):
            processing_time = None

        entry["status"] = status.value
        entry["end_time"] = end_time
        entry["processing_time"] = processing_time
        if dest_bucket is not None and dest_key is not None:
            entry["destination"] = {"bucket": dest_bucket, "key": dest_key}
        if error_message is not None:
            entry["error_message"] = error_message

        self._table.update_item(
            Key=key,
            UpdateExpression=(
                f"SET stage_progress[{idx}] = :entry, current_status = :status, updated_at = :now"
            ),
            ExpressionAttributeValues={
                ":entry": entry,
                ":status": upload_status.value,
                ":now": end_time,
            },
        )
