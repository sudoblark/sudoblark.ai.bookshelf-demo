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
import re
import uuid
from typing import Any, AsyncGenerator, Optional

import boto3
from bookshelf_streaming_agent import BookshelfStreamingAgent
from common.tracker import BookshelfTracker, UploadStage
from fastapi import Request
from fastapi.responses import StreamingResponse
from isbn_toolset import (
    _normalize_isbn,
    _query_google_books,
    _query_openlibrary,
    calculate_confidence,
)

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

    async def _extract_ocr_text(self, bucket: str, key: str) -> dict:
        """Extract OCR text from image via Textract.

        Returns:
            Dict with extracted_text, confidence, and line_count.
        """
        try:
            response = self._textract.detect_document_text(
                Document={"S3Object": {"Bucket": bucket, "Name": key}}
            )

            blocks = response.get("Blocks", [])
            lines = []

            for block in blocks:
                if block["BlockType"] == "LINE":
                    text = block.get("Text", "")
                    confidence = block.get("Confidence", 0)
                    if text and confidence > 50:
                        lines.append({"text": text, "confidence": confidence})

            extracted_text = "\n".join([line["text"] for line in lines])
            avg_confidence = sum(line["confidence"] for line in lines) / len(lines) if lines else 0

            logger.info(
                f"Extracted {len(lines)} lines from book cover via Textract "
                f"(avg confidence: {avg_confidence:.1f}%)"
            )

            return {
                "extracted_text": extracted_text,
                "confidence": avg_confidence / 100,  # Normalize to 0-1
                "line_count": len(lines),
            }
        except Exception as e:
            logger.exception("Failed to extract OCR text via Textract")
            return {"extracted_text": "", "confidence": 0.0, "line_count": 0, "error": str(e)}

    async def _extract_isbn(self, extracted_text: str) -> Optional[str]:
        """Extract ISBN from OCR text using regex patterns.

        Looks for ISBN-10 or ISBN-13 patterns in text.
        """
        # ISBN-13 pattern: 978 or 979 followed by 10 digits
        isbn13_pattern = r"(?:978|979)[- ]?(?:\d[- ]?){10}[\dX]"
        # ISBN-10 pattern: 9 digits followed by digit or X
        isbn10_pattern = r"(?:\d[- ]?){9}[\dX]"

        for pattern in [isbn13_pattern, isbn10_pattern]:
            match = re.search(pattern, extracted_text, re.IGNORECASE)
            if match:
                isbn = match.group(0)
                normalized = _normalize_isbn(isbn)
                # Validate it's actually a valid ISBN format
                if re.match(r"^(?:97[89]\d{10}|[0-9]{10}[X0-9])$", normalized):
                    return normalized
        return None

    async def _lookup_isbn_metadata(self, isbn: str) -> Optional[dict]:
        """Look up book metadata from ISBN using Google Books or Open Library APIs.

        Returns:
            Dict with title, authors, publisher, published_date, description, source.
        """
        if not isbn:
            return None

        try:
            # Try Google Books first
            logger.info(f"Querying Google Books API for ISBN {isbn}")
            result = _query_google_books(isbn, timeout=5.0)
            if result:
                return result

            # Fallback to Open Library
            logger.info(f"Google Books returned no results, trying Open Library for ISBN {isbn}")
            result = _query_openlibrary(isbn, timeout=5.0)
            if result:
                return result

            logger.warning(f"ISBN {isbn} not found in Google Books or Open Library")
            return None
        except Exception as e:
            logger.exception(f"ISBN lookup error: {e}")
            return None

    async def _lookup_by_title_author(
        self, title: str, author: str, publisher: str = ""
    ) -> Optional[dict]:
        """Fallback: look up ISBN using title/author extracted from OCR.

        This is used when ISBN is not visible on the cover but we have title/author.
        We construct a search query and try Google Books first, then Open Library.

        Returns:
            Dict with isbn, title, authors, publisher, published_date, description, source.
        """
        if not title or not author:
            return None

        try:
            # Build a query: "title author" or "title author publisher"
            query = f"{title} {author}"
            if publisher:
                query += f" {publisher}"

            logger.info(f"Attempting title/author lookup: {query}")

            # Query Google Books with title/author
            url = f"https://www.googleapis.com/books/v1/volumes?q={query.replace(' ', '+')}"
            import httpx

            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()

            if data.get("totalItems", 0) > 0:
                item = data["items"][0]
                volume_info = item.get("volumeInfo", {})
                identifiers = item.get("volumeInfo", {}).get("industryIdentifiers", [])

                # Extract ISBN-13 if available
                isbn = None
                for identifier in identifiers:
                    if identifier.get("type") == "ISBN_13":
                        isbn = identifier.get("identifier")
                        break
                if not isbn and identifiers:
                    isbn = identifiers[0].get("identifier")

                result = {
                    "isbn": isbn,
                    "title": volume_info.get("title", ""),
                    "authors": ", ".join(volume_info.get("authors", [])),
                    "publisher": volume_info.get("publisher", ""),
                    "published_date": volume_info.get("publishedDate", ""),
                    "description": volume_info.get("description", ""),
                    "source": "Google Books API (title/author lookup)",
                }
                logger.info(f"Title/author lookup found: {result['title']} ({result['isbn']})")
                return result

            logger.info(
                "Google Books title/author lookup returned no results, skipping Open Library fallback for title/author"
            )
            return None

        except Exception as e:
            logger.warning(f"Title/author lookup error: {e}")
            return None

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

        # Perform upfront data extraction: OCR + ISBN lookup
        # This reduces agent complexity and avoids rate limiting from excessive tool calls
        ocr_data = await self._extract_ocr_text(bucket, key)
        extracted_text = ocr_data.get("extracted_text", "")
        ocr_confidence = ocr_data.get("confidence", 0.0)

        isbn_from_cover = await self._extract_isbn(extracted_text)
        isbn_metadata = None
        if isbn_from_cover:
            isbn_metadata = await self._lookup_isbn_metadata(isbn_from_cover)

        # Build context-rich prompt without tools
        # Agent's job is now to categorize metadata, not to extract or look things up
        context_parts = [
            f"Book cover filename: {filename}",
            f"OCR-extracted text from cover:\n{extracted_text}",
            f"OCR confidence: {ocr_confidence:.2%}",
        ]

        if isbn_from_cover:
            context_parts.append(f"ISBN found on cover: {isbn_from_cover}")

        if isbn_metadata:
            context_parts.extend(
                [
                    f"ISBN lookup results from {isbn_metadata.get('source', 'API')}:",
                    f"  Title: {isbn_metadata.get('title', 'N/A')}",
                    f"  Authors: {isbn_metadata.get('authors', 'N/A')}",
                    f"  Publisher: {isbn_metadata.get('publisher', 'N/A')}",
                    f"  Published: {isbn_metadata.get('published_date', 'N/A')}",
                    f"  Description: {isbn_metadata.get('description', 'N/A')}",
                ]
            )

        context = "\n".join(context_parts)
        prompt = f"Here is the extracted data:\n\n{context}"

        # No toolsets - agent receives only context and does categorization
        toolsets = []

        # Create tracking record and mark USER_UPLOAD as complete (file already landed via presigned URL)
        try:
            self._tracker.create_record(user_id, upload_id)
            self._tracker.start_stage(upload_id, UploadStage.USER_UPLOAD, bucket, key)
            self._tracker.complete_stage(user_id, upload_id, UploadStage.USER_UPLOAD, bucket, key)
        except Exception:
            logger.exception("Failed to initialize tracking for upload_id=%s", upload_id)

        return StreamingResponse(
            self._stream_events(prompt, toolsets, upload_id, user_id, bucket, key, ocr_confidence),
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
        ocr_confidence: float = 0.0,
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

        # Fallback ISBN lookup: if agent found title/author but no ISBN,
        # attempt to look up using those extracted values
        if not prev_fields.get("isbn") and (prev_fields.get("title") or prev_fields.get("author")):
            logger.info("No ISBN found; attempting fallback title/author lookup")
            lookup_result = await self._lookup_by_title_author(
                title=str(prev_fields.get("title", "")),
                author=str(prev_fields.get("author", "")),
                publisher=str(prev_fields.get("publisher", "")),
            )

            if lookup_result:
                # Emit updates for any newly found fields
                for field in ["isbn", "publisher", "description"]:
                    new_value = lookup_result.get(field)
                    if new_value and not prev_fields.get(field):
                        prev_fields[field] = new_value
                        yield _sse("metadata_update", {"field": field, "value": new_value})

                # Extract published_year from published_date if available
                published_date = lookup_result.get("published_date", "")
                if published_date and not prev_fields.get("published_year"):
                    try:
                        # Try to extract year from dates like "2003", "2003-06-15", etc.
                        year = int(published_date.split("-")[0])
                        prev_fields["published_year"] = year
                        yield _sse("metadata_update", {"field": "published_year", "value": year})
                    except (ValueError, IndexError):
                        pass

                # Recalculate confidence if we found an ISBN
                if lookup_result.get("isbn"):
                    fields_with_isbn = list(prev_fields.keys())
                    new_confidence = calculate_confidence(
                        "inferred", fields_with_isbn, ocr_confidence
                    )
                    if new_confidence != prev_fields.get("confidence"):
                        prev_fields["confidence"] = new_confidence
                        yield _sse(
                            "metadata_update", {"field": "confidence", "value": new_confidence}
                        )

        yield _sse("complete", {})


def _sse(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"
