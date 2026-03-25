"""
Lambda function to route single image files from the landing bucket to the raw bucket.

Triggered by S3 ObjectCreated events on landing/uploads/{user_id}/{upload_id}/{filename}.
Validates the key format, filters by supported image extension, copies the file to the
raw bucket preserving the full S3 key, then deletes the source object.
"""

import logging
import os
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

s3_client = boto3.client("s3")

SUPPORTED_EXTENSIONS: frozenset = frozenset({".jpg", ".jpeg", ".png"})


def get_config() -> Dict[str, str]:
    """Load and validate configuration from environment variables."""
    raw_bucket: str = os.environ.get("RAW_BUCKET", "")
    if not raw_bucket:
        raise ValueError("RAW_BUCKET environment variable is required")
    return {"raw_bucket": raw_bucket}


def resolve_raw_bucket(source_bucket: str, raw_bucket_name: str) -> str:
    """
    Derive the full raw bucket name from the source bucket name.

    The naming convention is account-project-application-{tier}, so we strip
    the last segment and append the target tier name.
    """
    parts: List[str] = source_bucket.split("-")
    if len(parts) < 4:
        raise ValueError(f"Invalid source bucket name format: {source_bucket}")
    prefix = "-".join(parts[:-1])
    return f"{prefix}-{raw_bucket_name}"


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


@event_source(data_class=S3Event)
def handler(event: S3Event, context: Any) -> Dict[str, Any]:
    """
    Route a single image file from the landing bucket to the raw bucket.

    Validates the S3 key format and file extension, copies the object to the raw
    bucket preserving the key, then deletes the source.
    """
    config = get_config()

    processed_files: List[str] = []
    failed_files: List[Dict[str, str]] = []

    for record in event.records:
        source_key: str = record.s3.get_object.key
        try:
            source_bucket: str = record.s3.bucket.name

            if ".." in source_key:
                raise ValueError(f"Invalid S3 key (path traversal): {source_key}")

            _, _, filename = parse_upload_key(source_key)

            if not is_supported_extension(filename):
                raise ValueError(f"Unsupported file extension for key: {source_key}")

            raw_bucket = resolve_raw_bucket(source_bucket, config["raw_bucket"])

            logger.info(
                f"Routing s3://{source_bucket}/{source_key} to s3://{raw_bucket}/{source_key}"
            )

            s3_client.copy_object(
                CopySource={"Bucket": source_bucket, "Key": source_key},
                Bucket=raw_bucket,
                Key=source_key,
            )

            s3_client.delete_object(Bucket=source_bucket, Key=source_key)
            logger.info(f"Deleted source: s3://{source_bucket}/{source_key}")

            processed_files.append(source_key)
            logger.info(f"Routed to raw: {source_key}")

        except Exception as e:
            logger.error(f"Failed to process {source_key}: {str(e)}", exc_info=True)
            failed_files.append({"key": source_key, "error": str(e)})

    return {
        "statusCode": 200 if not failed_files else 207,
        "processed_count": len(processed_files),
        "failed_count": len(failed_files),
        "processed_files": processed_files,
        "failed_files": failed_files,
    }
