"""Metadata extraction toolset for book cataloging agent.

Provides tools for:
- Extracting OCR text from book cover images
- Extracting ISBN patterns from OCR text
- Looking up book metadata via ISBN
- Looking up book metadata via title/author (fallback)
- Updating individual metadata fields based on user corrections

This toolset enables the agent to have full agency over the extraction
and refinement process, with each tool call tracked for transparency.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

import httpx
from isbn_toolset import _normalize_isbn, _query_google_books, _query_openlibrary
from pydantic_ai import FunctionToolset
from tool_tracker import ToolTracker

logger = logging.getLogger(__name__)


def build_metadata_toolset(
    s3_client: Any,
    textract_client: Any,
    bucket: str,
    key: str,
    tracker: Optional[ToolTracker] = None,
) -> FunctionToolset:
    """Build a toolset for metadata extraction with full agent agency.

    Args:
        s3_client: Boto3 S3 client
        textract_client: Boto3 Textract client
        bucket: S3 bucket containing the book cover image
        key: S3 object key for the book cover image
        tracker: Optional ToolTracker for recording tool executions

    Returns:
        FunctionToolset with metadata extraction and update tools
    """
    toolset = FunctionToolset()

    # Track call counts to enforce limits per request
    call_counts = {
        "extract_ocr_text": 0,
        "extract_isbn": 0,
        "lookup_isbn_metadata": 0,
        "lookup_by_title_author": 0,
    }

    @toolset.tool_plain
    def extract_ocr_text() -> Dict:
        """Extract text from book cover using AWS Textract OCR.

        Returns a dict with:
        - extracted_text: The full OCR text from the cover
        - confidence: Average confidence of text lines (0.0-1.0)
        - line_count: Number of high-confidence text lines extracted

        This tool can only be called once per request.
        """
        if call_counts["extract_ocr_text"] >= 1:
            return {"error": "OCR extraction already completed"}

        start = time.time()
        try:
            response = textract_client.detect_document_text(
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

            result = {
                "extracted_text": extracted_text,
                "confidence": avg_confidence / 100,  # Normalize to 0-1
                "line_count": len(lines),
            }

            elapsed_ms = (time.time() - start) * 1000
            if tracker:
                tracker.record(
                    tool_name="extract_ocr_text",
                    inputs_str=f"s3://{bucket}/{key}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(f"Extracted {len(lines)} lines via Textract ({elapsed_ms:.1f}ms)")
            call_counts["extract_ocr_text"] += 1
            return result

        except Exception as e:
            logger.exception("Failed to extract OCR text")
            elapsed_ms = (time.time() - start) * 1000
            result = {"error": str(e)}
            if tracker:
                tracker.record(
                    tool_name="extract_ocr_text",
                    inputs_str=f"s3://{bucket}/{key}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            return result

    @toolset.tool_plain
    def extract_isbn(ocr_text: str) -> Dict:
        """Extract ISBN number from OCR text using regex patterns.

        Args:
            ocr_text: The OCR-extracted text from the book cover

        Returns a dict with:
        - isbn: The found ISBN (if any), or None
        - pattern_matched: The regex pattern that matched (for debugging)

        Looks for ISBN-10 or ISBN-13 patterns. Can only be called once per request.
        """
        if call_counts["extract_isbn"] >= 1:
            return {"error": "ISBN extraction already completed"}

        start = time.time()
        try:
            # ISBN-13 pattern: 978 or 979 followed by 10 digits
            isbn13_pattern = r"(?:978|979)[- ]?(?:\d[- ]?){10}[\dX]"
            # ISBN-10 pattern: 9 digits followed by digit or X
            isbn10_pattern = r"(?:\d[- ]?){9}[\dX]"

            for pattern_name, pattern in [("ISBN-13", isbn13_pattern), ("ISBN-10", isbn10_pattern)]:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    isbn = match.group(0)
                    normalized = _normalize_isbn(isbn)
                    # Validate format
                    if re.match(r"^(?:97[89]\d{10}|[0-9]{10}[X0-9])$", normalized):
                        result: Dict[str, Any] = {
                            "isbn": normalized,
                            "pattern_matched": pattern_name,
                        }
                        elapsed_ms = (time.time() - start) * 1000
                        if tracker:
                            tracker.record(
                                tool_name="extract_isbn",
                                inputs_str=f"{len(ocr_text)} chars of OCR text",
                                result=result,
                                execution_time_ms=elapsed_ms,
                            )
                        logger.info(f"Found ISBN: {normalized} ({pattern_name})")
                        call_counts["extract_isbn"] += 1
                        return result

            result = {"isbn": None}
            elapsed_ms = (time.time() - start) * 1000
            if tracker:
                tracker.record(
                    tool_name="extract_isbn",
                    inputs_str=f"{len(ocr_text)} chars of OCR text",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            logger.info("No ISBN pattern found in OCR text")
            call_counts["extract_isbn"] += 1
            return result

        except Exception as e:
            logger.exception("Failed to extract ISBN")
            elapsed_ms = (time.time() - start) * 1000
            result = {"error": str(e)}
            if tracker:
                tracker.record(
                    tool_name="extract_isbn",
                    inputs_str=f"{len(ocr_text)} chars of OCR text",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            return result

    @toolset.tool_plain
    def lookup_isbn_metadata(isbn: str) -> Dict:
        """Look up book metadata from ISBN using Google Books or Open Library APIs.

        Args:
            isbn: The ISBN to look up

        Returns a dict with book metadata if found:
        - title: Book title
        - authors: Author names
        - publisher: Publisher name
        - published_date: Publication date
        - description: Book description
        - source: Which API provided the result

        Can only be called once per request. Tries Google Books first, falls back to Open Library.
        """
        if call_counts["lookup_isbn_metadata"] >= 1:
            return {"error": "ISBN metadata lookup already completed"}

        if not isbn:
            return {"error": "ISBN is required"}

        start = time.time()
        try:
            logger.info(f"Looking up ISBN {isbn} via Google Books")
            result = _query_google_books(isbn, timeout=5.0)
            if result:
                elapsed_ms = (time.time() - start) * 1000
                if tracker:
                    tracker.record(
                        tool_name="lookup_isbn_metadata",
                        inputs_str=f"ISBN: {isbn}",
                        result=result,
                        execution_time_ms=elapsed_ms,
                    )
                logger.info(f"Found ISBN {isbn} in Google Books: {result.get('title')}")
                call_counts["lookup_isbn_metadata"] += 1
                return result

            logger.info(f"ISBN {isbn} not in Google Books, trying Open Library")
            result = _query_openlibrary(isbn, timeout=5.0)
            if result:
                elapsed_ms = (time.time() - start) * 1000
                if tracker:
                    tracker.record(
                        tool_name="lookup_isbn_metadata",
                        inputs_str=f"ISBN: {isbn}",
                        result=result,
                        execution_time_ms=elapsed_ms,
                    )
                logger.info(f"Found ISBN {isbn} in Open Library: {result.get('title')}")
                call_counts["lookup_isbn_metadata"] += 1
                return result

            result = {"error": f"ISBN {isbn} not found in any database"}
            elapsed_ms = (time.time() - start) * 1000
            if tracker:
                tracker.record(
                    tool_name="lookup_isbn_metadata",
                    inputs_str=f"ISBN: {isbn}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            logger.warning(f"ISBN {isbn} not found anywhere")
            call_counts["lookup_isbn_metadata"] += 1
            return result

        except Exception as e:
            logger.exception(f"ISBN lookup error for {isbn}")
            elapsed_ms = (time.time() - start) * 1000
            result = {"error": str(e)}
            if tracker:
                tracker.record(
                    tool_name="lookup_isbn_metadata",
                    inputs_str=f"ISBN: {isbn}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            return result

    @toolset.tool_plain
    def lookup_by_title_author(title: str, author: str, publisher: str = "") -> Dict:
        """Fallback: look up ISBN using title and author extracted from OCR.

        Use this when the ISBN is not visible on the cover but you have extracted title/author.

        Args:
            title: Book title from OCR
            author: Author name from OCR
            publisher: Optional publisher name

        Returns a dict with book metadata if found, or error dict.

        Can only be called once per request.
        """
        if call_counts["lookup_by_title_author"] >= 1:
            return {"error": "Title/author lookup already completed"}

        if not title or not author:
            return {"error": "Title and author are required"}

        start = time.time()
        try:
            query = f"{title} {author}"
            if publisher:
                query += f" {publisher}"

            logger.info(f"Attempting title/author lookup: {query}")

            url = f"https://www.googleapis.com/books/v1/volumes?q={query.replace(' ', '+')}"
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()

            if data.get("totalItems", 0) > 0:
                item = data["items"][0]
                volume_info = item.get("volumeInfo", {})
                identifiers = volume_info.get("industryIdentifiers", [])

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
                    "source": "Google Books API (title/author)",
                }
                elapsed_ms = (time.time() - start) * 1000
                if tracker:
                    tracker.record(
                        tool_name="lookup_by_title_author",
                        inputs_str=f"Title: {title}, Author: {author}",
                        result=result,
                        execution_time_ms=elapsed_ms,
                    )
                logger.info(f"Title/author lookup found: {result['title']}")
                call_counts["lookup_by_title_author"] += 1
                return result

            result = {"error": "No matches found"}
            elapsed_ms = (time.time() - start) * 1000
            if tracker:
                tracker.record(
                    tool_name="lookup_by_title_author",
                    inputs_str=f"Title: {title}, Author: {author}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            logger.info("Title/author lookup returned no results")
            call_counts["lookup_by_title_author"] += 1
            return result

        except Exception as e:
            logger.exception("Title/author lookup error")
            elapsed_ms = (time.time() - start) * 1000
            result = {"error": str(e)}
            if tracker:
                tracker.record(
                    tool_name="lookup_by_title_author",
                    inputs_str=f"Title: {title}, Author: {author}",
                    result=result,
                    execution_time_ms=elapsed_ms,
                )
            return result

    @toolset.tool_plain
    def update_metadata_field(field: str, value: str) -> Dict:
        """Update a specific metadata field based on user correction.

        Args:
            field: Field name to update (title, author, isbn, publisher, published_year, description)
            value: New value for the field

        Returns a dict confirming the update.

        This tool can be called multiple times as the user refines the metadata.
        """
        valid_fields = ["title", "author", "isbn", "publisher", "published_year", "description"]
        if field not in valid_fields:
            return {"error": f"Invalid field: {field}. Valid fields are: {', '.join(valid_fields)}"}

        if not value or not value.strip():
            return {"error": "Value cannot be empty"}

        start = time.time()
        result = {"field": field, "value": value.strip(), "status": "updated"}

        elapsed_ms = (time.time() - start) * 1000
        if tracker:
            tracker.record(
                tool_name="update_metadata_field",
                inputs_str=f"{field} = {value.strip()}",
                result=result,
                execution_time_ms=elapsed_ms,
            )

        logger.info(f"Updated {field} to: {value.strip()}")
        return result

    return toolset
