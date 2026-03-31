"""Shared S3 utilities for bookshelf-demo Lambda functions."""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def parse_upload_key(key: str) -> Tuple[str, str, str]:
    """Parse user_id, upload_id, and filename from an S3 upload key.

    Expected format: ``uploads/{user_id}/{upload_id}/{filename}``

    Args:
        key: S3 object key.

    Returns:
        Tuple of (user_id, upload_id, filename).

    Raises:
        ValueError: If *key* does not match the expected format.
    """
    parts = key.split("/")
    if len(parts) != 4 or parts[0] != "uploads":
        raise ValueError(
            f"Key does not match expected format uploads/user_id/upload_id/filename: {key}"
        )
    _, user_id, upload_id, filename = parts
    return user_id, upload_id, filename


def validate_key(key: str) -> None:
    """Reject S3 keys containing path traversal sequences.

    Args:
        key: S3 object key to validate.

    Raises:
        ValueError: If *key* contains ``..``.
    """
    if ".." in key:
        raise ValueError(f"Invalid S3 key (path traversal): {key}")
