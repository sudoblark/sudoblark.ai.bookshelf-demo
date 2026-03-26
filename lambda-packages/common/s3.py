"""Shared S3 utilities for bookshelf-demo Lambda functions."""

import logging
from typing import List, Tuple

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


def resolve_bucket(source_bucket: str, tier: str) -> str:
    """Derive a full bucket name from the source bucket's naming convention.

    The convention is ``account-project-application-{tier}``. Strips the last
    dash-delimited segment of *source_bucket* and appends *tier*.

    Args:
        source_bucket: Full name of the source bucket.
        tier: Target tier name (e.g. ``"raw"``, ``"processed"``).

    Returns:
        Full name of the target bucket.

    Raises:
        ValueError: If *source_bucket* has fewer than four dash-delimited segments.
    """
    parts: List[str] = source_bucket.split("-")
    if len(parts) < 4:
        raise ValueError(f"Invalid source bucket name format: {source_bucket}")
    prefix = "-".join(parts[:-1])
    return f"{prefix}-{tier}"


def validate_key(key: str) -> None:
    """Reject S3 keys containing path traversal sequences.

    Args:
        key: S3 object key to validate.

    Raises:
        ValueError: If *key* contains ``..``.
    """
    if ".." in key:
        raise ValueError(f"Invalid S3 key (path traversal): {key}")
