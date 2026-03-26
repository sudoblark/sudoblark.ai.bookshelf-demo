"""
Lambda function to route single image files from the landing bucket to the raw bucket.

Triggered by S3 ObjectCreated events on landing/uploads/{user_id}/{upload_id}/{filename}.
Validates the key format, filters by supported image extension, copies the file to the
raw bucket preserving the full S3 key, then deletes the source object.
"""

import os
from typing import Any, Tuple

from common.handler import BaseS3BatchHandler
from common.s3 import resolve_bucket
from common.tracker import BookshelfTracker, UploadStage

SUPPORTED_EXTENSIONS: frozenset = frozenset({".jpg", ".jpeg", ".png"})


def parse_upload_key(key: str) -> Tuple[str, str, str]:
    """
    Parse user_id, upload_id, and filename from the S3 key.

    Expected format: uploads/{user_id}/{upload_id}/{filename}

    Returns:
        Tuple of (user_id, upload_id, filename).

    Raises:
        ValueError: If the key does not match the expected format.
    """
    parts = key.split("/")
    if len(parts) != 4 or parts[0] != "uploads":
        raise ValueError(
            f"Key does not match expected format uploads/user_id/upload_id/filename: {key}"
        )
    _, user_id, upload_id, filename = parts
    return user_id, upload_id, filename


def is_supported_extension(filename: str) -> bool:
    """Return True if the filename has a supported image extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


class FileRouterHandler(BaseS3BatchHandler):
    """Routes single image uploads from the landing bucket to the raw bucket."""

    def __init__(self, s3_client: Any = None, tracker: Any = None) -> None:
        super().__init__(s3_client)
        raw_bucket: str = os.environ.get("RAW_BUCKET", "")
        if not raw_bucket:
            raise ValueError("RAW_BUCKET environment variable is required")
        self._raw_bucket_tier = raw_bucket
        if tracker is not None:
            self._tracker = tracker
        else:
            tracking_table = os.environ.get("TRACKING_TABLE", "")
            if not tracking_table:
                raise ValueError("TRACKING_TABLE environment variable is required")
            self._tracker = BookshelfTracker(table_name=tracking_table)

    def process_record(self, bucket: str, key: str) -> str:
        user_id, upload_id, filename = parse_upload_key(key)
        if not is_supported_extension(filename):
            raise ValueError(f"Unsupported file extension for key: {key}")

        raw_bucket = resolve_bucket(bucket, self._raw_bucket_tier)
        self.logger.info(f"Routing s3://{bucket}/{key} to s3://{raw_bucket}/{key}")

        self._tracker.create_record(user_id, upload_id, filename, bucket, key)
        self._tracker.start_stage(user_id, upload_id, filename, UploadStage.ROUTING, bucket, key)

        try:
            self.s3_client.copy_object(
                CopySource={"Bucket": bucket, "Key": key},
                Bucket=raw_bucket,
                Key=key,
            )
            self.s3_client.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:
            self._tracker.fail_stage(user_id, upload_id, filename, UploadStage.ROUTING, str(exc))
            raise

        self._tracker.complete_stage(
            user_id, upload_id, filename, UploadStage.ROUTING, raw_bucket, key
        )
        self.logger.info(f"Deleted source: s3://{bucket}/{key}")
        return key


handler = FileRouterHandler()
