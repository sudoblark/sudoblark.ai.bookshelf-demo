"""Orchestration layer for POST /api/metadata/initial.

One-shot cold classification of a newly uploaded book cover.  The handler:

1. Parses ``{bucket, key, filename}`` from the request body.
2. Builds an S3 chunked-reader toolset (reused from the bookshelf-agent layer).
3. Streams the ``BookshelfStreamingAgent`` response as SSE.
4. Tracks upload progress in DynamoDB: creates record on first call, marks stages.

SSE event types emitted
-----------------------
text_delta       ``{"type": "text_delta", "delta": "<text>"}``
metadata_update  ``{"type": "metadata_update", "field": "<name>", "value": <val>}``
complete         ``{"type": "complete"}``
error            ``{"type": "error", "message": "<reason>"}``
"""

import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Optional

import boto3
from bookshelf_streaming_agent import BookshelfStreamingAgent
from common.tracker import BookshelfTracker, UploadStage
from fastapi import Request
from fastapi.responses import StreamingResponse
from image_toolset import build_image_toolset
from isbn_toolset import build_isbn_toolset

logger = logging.getLogger(__name__)

_METADATA_FIELDS = (
    "title",
    "author",
    "isbn",
    "publisher",
    "published_year",
    "description",
    "confidence",
)


class MetadataInitialHandler:
    """Handles the full lifecycle of an initial metadata extraction request."""

    def __init__(
        self,
        agent: Optional[BookshelfStreamingAgent] = None,
        s3_client: Any = None,
        textract_client: Any = None,
        dynamodb_resource: Any = None,
    ) -> None:
        self._model_id: str = os.environ["BEDROCK_MODEL_ID"]
        region: str = os.environ.get(
            "BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
        )
        self._s3 = s3_client or boto3.client("s3")
        self._textract = textract_client or boto3.client("textract", region_name=region)

        if agent is None:
            bedrock_client = boto3.client("bedrock-runtime", region_name=region)
            agent = BookshelfStreamingAgent(model_id=self._model_id, bedrock_client=bedrock_client)
        self._agent = agent

        # DynamoDB tracking for ingestion pipeline
        self._tracker = BookshelfTracker(
            dynamodb_resource=dynamodb_resource,
            table_name=os.environ.get("TRACKING_TABLE", ""),
        )

    async def handle(self, request: Request) -> StreamingResponse:
        """Parse body, build toolset, and return a streaming SSE response."""
        try:
            body = await request.json()
        except Exception:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Invalid JSON body")

        bucket: Optional[str] = body.get("bucket")
        key: Optional[str] = body.get("key")
        filename: str = body.get("filename", "book cover")

        if not bucket or not key:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="bucket and key are required")

        # Generate a unique upload_id for this extraction session.
        # This is returned to the client for subsequent refinement/accept calls.
        upload_id = str(uuid.uuid4())
        user_id = "anonymous"  # TODO: extract from auth context in production

        # Build the image toolset for efficient extraction via Textract OCR and ISBN toolset.
        try:
            image_toolset = build_image_toolset(self._s3, bucket, key, self._textract)
            isbn_toolset = build_isbn_toolset(enable_lookup=True)
            toolsets = [image_toolset, isbn_toolset]
        except Exception:  # pragma: no cover
            logger.exception("Failed to build toolsets")
            toolsets = []

        prompt = (
            f"Extract book metadata from the image at s3://{bucket}/{key} (filename: {filename}). "
            "Use the file-reading tools to inspect the image, then return all metadata fields."
        )

        # Create tracking record and mark USER_UPLOAD as complete (file already landed via presigned URL)
        try:
            self._tracker.create_record(user_id, upload_id)
            self._tracker.start_stage(upload_id, UploadStage.USER_UPLOAD, bucket, key)
            self._tracker.complete_stage(user_id, upload_id, UploadStage.USER_UPLOAD, bucket, key)
        except Exception:
            logger.exception("Failed to initialize tracking for upload_id=%s", upload_id)

        return StreamingResponse(
            self._stream_events(prompt, toolsets, upload_id, user_id, bucket, key),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    async def _stream_events(  # pragma: no cover
        self,
        prompt: str,
        toolsets: Any,
        upload_id: str,
        user_id: str,
        bucket: str,
        key: str,
    ) -> AsyncGenerator[str, None]:
        prev_msg = ""
        prev_fields: dict = {}

        # Emit the upload_id immediately so client can track this session
        yield _sse("upload_id", {"upload_id": upload_id})

        # Start the ENRICHMENT stage (extraction + refinement + acceptance)
        try:
            self._tracker.start_stage(upload_id, UploadStage.ENRICHMENT, bucket, key)
        except Exception:
            logger.exception(
                "Failed to mark ENRICHMENT stage as started for upload_id=%s", upload_id
            )

        try:
            async with self._agent.run_stream(
                prompt,
                toolsets=toolsets,
            ) as result:
                async for partial in result.stream_output():
                    # Stream assistant message deltas
                    current_msg: str = partial.assistantMessage or ""
                    if len(current_msg) > len(prev_msg):
                        yield _sse("text_delta", {"delta": current_msg[len(prev_msg) :]})
                        prev_msg = current_msg

                    # Stream metadata field updates as they solidify
                    for field in _METADATA_FIELDS:
                        value = getattr(partial, field, None)

                        # GUARD: If ISBN field and it's not visible on cover, force it to empty
                        if field == "isbn" and value:
                            # ISBN should only be populated if it was directly visible
                            # The AI should not infer/hallucinate ISBNs
                            logger.warning(
                                f"Agent attempted to set ISBN to '{value}' - clearing to prevent hallucination. "
                                f"ISBN must only come from the barcode or user input."
                            )
                            value = ""

                        if value != prev_fields.get(field):
                            prev_fields[field] = value
                            yield _sse("metadata_update", {"field": field, "value": value})

        except Exception as exc:  # pragma: no cover
            logger.exception("Agent stream error during initial extraction: %s", exc)
            try:
                # Mark the ENRICHMENT stage as failed in DynamoDB
                self._tracker.fail_stage(
                    user_id=user_id,
                    upload_id=upload_id,
                    stage=UploadStage.ENRICHMENT,
                    error_message=f"Bedrock API error: {str(exc)}",
                )
            except Exception:
                logger.exception(
                    "Failed to mark ENRICHMENT stage as failed for upload_id=%s", upload_id
                )
            yield _sse("error", {"message": "Agent error — please try again"})
            return

        yield _sse("complete", {})


def _sse(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
