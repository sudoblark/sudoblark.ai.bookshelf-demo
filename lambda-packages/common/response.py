"""Shared Lambda response builder for S3 batch-processing functions."""
from typing import Any, Dict, List


def build_response(
    processed: List[str],
    failed: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Build a standardised Lambda response for S3 batch processing.

    Returns HTTP 200 when all records succeeded, 207 (Multi-Status) when at
    least one record failed.

    Args:
        processed: Keys of successfully processed S3 objects.
        failed: Dicts with ``"key"`` and ``"error"`` for each failure.

    Returns:
        Response dict with statusCode, processed_count, failed_count,
        processed_files, and failed_files.
    """
    return {
        "statusCode": 200 if not failed else 207,
        "processed_count": len(processed),
        "failed_count": len(failed),
        "processed_files": processed,
        "failed_files": failed,
    }
