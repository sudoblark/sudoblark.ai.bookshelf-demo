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
from common.tracker import BookshelfTracker, UploadStage
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _sanitise(value: str) -> str:
    """Replace characters that are invalid in S3 Hive partition values."""
    return re.sub(r"[^a-zA-Z0-9 _\-.]", "_", value).strip() or "unknown"


class AcceptHandler:
    """Saves accepted metadata to S3 with Hive-style partitioning."""

    def __init__(
        self,
        s3_client: Any = None,
        dynamodb_resource: Any = None,
        sfn_client: Any = None,
    ) -> None:
        self._s3 = s3_client or boto3.client("s3")
        self._sfn = sfn_client or boto3.client("stepfunctions")
        self._enrichment_state_machine_arn: str = os.environ.get("ENRICHMENT_STATE_MACHINE_ARN", "")
        self._raw_bucket: str = os.environ["RAW_BUCKET"]
        self._tracker = BookshelfTracker(
            dynamodb_resource=dynamodb_resource,
            table_name=os.environ.get("TRACKING_TABLE", ""),
        )

    def _trigger_enrichment(self, upload_id: str) -> None:
        """Fire the enrichment state machine for the given upload_id (non-fatal)."""
        if not self._enrichment_state_machine_arn:
            return
        try:
            self._sfn.start_execution(
                stateMachineArn=self._enrichment_state_machine_arn,
                input=json.dumps({"upload_id": upload_id}),
            )
            logger.info("Triggered enrichment state machine for upload_id=%s", upload_id)
        except Exception:
            logger.warning("Failed to trigger enrichment state machine for upload_id=%s", upload_id)

    async def handle(self, request: Request) -> JSONResponse:
        """Write metadata JSON to the raw bucket and return the saved key."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        metadata: Optional[dict] = body.get("metadata")
        filename: str = body.get("filename", "unknown")
        upload_id: str = body.get("upload_id", "")

        if not metadata:
            raise HTTPException(status_code=400, detail="metadata is required")

        author = _sanitise(str(metadata.get("author", "unknown")))
        year = metadata.get("published_year") or "unknown"

        # If no upload_id provided, generate one (for backwards compatibility with old frontend)
        if not upload_id:
            upload_id = str(uuid.uuid4())

        key = f"author={author}/published_year={year}/{upload_id}.json"

        payload = json.dumps(
            {"filename": filename, "upload_id": upload_id, **metadata},
            indent=2,
            default=str,
        ).encode("utf-8")

        user_id = "anonymous"  # TODO: extract from auth context in production

        try:
            self._s3.put_object(
                Bucket=self._raw_bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
            )
        except Exception:
            logger.exception("Failed to write metadata to s3://%s/%s", self._raw_bucket, key)
            # Mark ANALYSED as failed
            if upload_id:
                try:
                    self._tracker.fail_stage(
                        user_id=user_id,
                        upload_id=upload_id,
                        stage=UploadStage.ANALYSED,
                        error_message="Failed to save metadata to S3",
                    )
                except Exception:
                    logger.exception(
                        "Failed to mark ANALYSED stage as failed for upload_id=%s", upload_id
                    )
            raise HTTPException(status_code=500, detail="Failed to save metadata")

        # Mark the ANALYSED stage as complete in DynamoDB after successful S3 write
        if upload_id:
            try:
                self._tracker.complete_stage(
                    user_id=user_id,
                    upload_id=upload_id,
                    stage=UploadStage.ANALYSED,
                    dest_bucket=self._raw_bucket,
                    dest_key=key,
                )
            except Exception:
                logger.exception(
                    "Failed to mark ANALYSED stage as complete for upload_id=%s", upload_id
                )

        logger.info("Saved metadata to s3://%s/%s", self._raw_bucket, key)

        if upload_id:
            self._trigger_enrichment(upload_id)

        return JSONResponse({"status": "accepted", "saved_key": key, "upload_id": upload_id})
