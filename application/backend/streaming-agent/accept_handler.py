"""Handler for POST /api/metadata/accept.

Saves accepted book metadata as JSON to the raw S3 bucket with Hive-style
partitioning: ``author={author}/published_year={year}/{uuid}.json``.

Request body
------------
metadata : dict
    All book metadata fields (title, author, isbn, publisher, published_year,
    description, confidence).
filename : str
    Original upload filename — stored in the JSON for provenance.

Response JSON
-------------
status     : "accepted"
saved_key  : Full S3 key where the JSON was written
upload_id  : UUID used as the filename stem
"""

import json
import logging
import os
import re
import uuid
from typing import Any, Optional

import boto3
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _sanitise(value: str) -> str:
    """Replace characters that are invalid in S3 Hive partition values."""
    return re.sub(r"[^a-zA-Z0-9 _\-.]", "_", value).strip() or "unknown"


class AcceptHandler:
    """Saves accepted metadata to S3 with Hive-style partitioning."""

    def __init__(self, s3_client: Any = None) -> None:
        self._s3 = s3_client or boto3.client("s3")
        self._raw_bucket: str = os.environ["RAW_BUCKET"]

    async def handle(self, request: Request) -> JSONResponse:
        """Write metadata JSON to the raw bucket and return the saved key."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        metadata: Optional[dict] = body.get("metadata")
        filename: str = body.get("filename", "unknown")

        if not metadata:
            raise HTTPException(status_code=400, detail="metadata is required")

        author = _sanitise(str(metadata.get("author", "unknown")))
        year = metadata.get("published_year") or "unknown"
        upload_id = str(uuid.uuid4())
        key = f"author={author}/published_year={year}/{upload_id}.json"

        payload = json.dumps(
            {"filename": filename, "upload_id": upload_id, **metadata},
            indent=2,
            default=str,
        ).encode("utf-8")

        try:
            self._s3.put_object(
                Bucket=self._raw_bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
            )
        except Exception:
            logger.exception("Failed to write metadata to s3://%s/%s", self._raw_bucket, key)
            raise HTTPException(status_code=500, detail="Failed to save metadata")

        logger.info("Saved metadata to s3://%s/%s", self._raw_bucket, key)
        return JSONResponse({"status": "accepted", "saved_key": key, "upload_id": upload_id})
