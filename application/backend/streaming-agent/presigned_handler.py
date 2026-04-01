"""Handler for GET /api/upload/presigned.

Generates a short-lived S3 pre-signed PUT URL so the browser can upload a
book cover image directly to the landing bucket without routing the binary
through this service.

The ``session_id`` returned in the response acts as the conversation key for
subsequent ``/api/metadata/initial`` and ``/api/metadata/refine`` calls.
"""

import logging
import os
import uuid
from typing import Any

import boto3
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class PresignedUrlHandler:
    """Generate pre-signed S3 PUT URLs for direct browser uploads."""

    def __init__(self, s3_client: Any = None) -> None:
        self._s3 = s3_client or boto3.client("s3")
        self._landing_bucket: str = os.environ["LANDING_BUCKET"]

    async def handle(self, request: Request) -> JSONResponse:
        """Return a pre-signed URL and the S3 key for the upload.

        Query parameters
        ----------------
        filename : str
            Original filename (e.g. ``cover.jpg``).

        Response JSON
        -------------
        url        : pre-signed PUT URL (1-hour expiry)
        key        : S3 object key — pass this to /api/metadata/initial
        bucket     : landing bucket name
        session_id : UUID identifying this upload session
        """
        filename = request.query_params.get("filename", "").strip()
        if not filename:
            return JSONResponse({"error": "filename query parameter is required"}, status_code=400)

        session_id = str(uuid.uuid4())
        key = f"ui/uploads/{session_id}/{filename}"

        try:
            url = self._s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._landing_bucket, "Key": key},
                ExpiresIn=3600,
            )
        except Exception:
            logger.exception("Failed to generate pre-signed URL for key=%s", key)
            return JSONResponse({"error": "Failed to generate upload URL"}, status_code=500)

        return JSONResponse(
            {
                "url": url,
                "key": key,
                "bucket": self._landing_bucket,
                "session_id": session_id,
            }
        )
