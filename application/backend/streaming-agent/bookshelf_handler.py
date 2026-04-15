"""Handler for bookshelf display endpoints.

Queries the S3 raw bucket (Hive-partitioned JSON) to serve bookshelf data.
See docs/adr/0001-bookshelf-storage-s3-query.md for architectural rationale.

Endpoints
---------
GET /bookshelf/overview
    High-level stats: total book count, most common author.
    Response: {"total_books": N, "most_common_author": str, "most_common_author_count": N}

GET /bookshelf/catalogue?page=1&page_size=5
    Paginated list of all books (default 5 per page, max 20).
    Response: {"books": [...], "page": N, "page_size": N, "total_books": N, "total_pages": N}

GET /bookshelf/search?query=X&field=title
    Filter books by title or author (case-insensitive substring match).
    Response: {"books": [...], "total_results": N, "query": str, "field": str}
"""

import json
import logging
import os
from collections import Counter
from typing import Any, Dict, List, Optional

import boto3
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _ok(body: Dict) -> JSONResponse:
    """Return 200 OK response with CORS headers."""
    return JSONResponse(body, status_code=200, headers=_CORS_HEADERS)


def _error(message: str) -> JSONResponse:
    """Return 500 error response with CORS headers."""
    return JSONResponse({"error": message}, status_code=500, headers=_CORS_HEADERS)


class BookshelfHandler:
    """REST handler for bookshelf display endpoints (querying S3)."""

    def __init__(self, s3_client: Optional[Any] = None) -> None:
        """Initialize handler with S3 client.

        Args:
            s3_client: Boto3 S3 client. If None, creates new client.
        """
        self._s3 = s3_client or boto3.client("s3")
        self._raw_bucket = os.environ["RAW_BUCKET"]

    def _list_all_books(self) -> List[Dict]:
        """Query S3 raw bucket and parse all book JSON files.

        Returns:
            List of book dicts, each with 'book_id' and 's3_key' added.
        """
        books = []
        try:
            paginator = self._s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._raw_bucket):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".json"):
                        try:
                            response = self._s3.get_object(Bucket=self._raw_bucket, Key=key)
                            data = json.loads(response["Body"].read())
                            # Add book_id and s3_key for response
                            data["s3_key"] = key
                            data["book_id"] = data.get(
                                "upload_id", key.split("/")[-1].replace(".json", "")
                            )
                            books.append(data)
                        except Exception as e:
                            logger.warning("Failed to parse S3 object %s: %s", key, e)
        except Exception as e:
            logger.exception("Error listing books from S3: %s", e)
            raise

        return books

    async def handle_overview(self, request: Request) -> JSONResponse:
        """GET /bookshelf/overview — Return high-level stats."""
        try:
            books = self._list_all_books()
            total_books = len(books)

            if total_books == 0:
                return _ok(
                    {"total_books": 0, "most_common_author": None, "most_common_author_count": 0}
                )

            # Count authors
            authors = [b["author"] for b in books if b.get("author")]
            author_counts = Counter(authors)
            most_common_author, count = (
                author_counts.most_common(1)[0] if author_counts else (None, 0)
            )

            return _ok(
                {
                    "total_books": total_books,
                    "most_common_author": most_common_author,
                    "most_common_author_count": count,
                }
            )
        except Exception as exc:
            logger.exception("Error in overview: %s", exc)
            return _error(str(exc))

    async def handle_catalogue(self, request: Request) -> JSONResponse:
        """GET /bookshelf/catalogue — Return paginated books."""
        try:
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 5)), 20)

            books = self._list_all_books()
            total_books = len(books)
            total_pages = (total_books + page_size - 1) // page_size  # Ceiling division

            # Paginate
            start = (page - 1) * page_size
            end = start + page_size
            page_books = books[start:end]

            return _ok(
                {
                    "books": page_books,
                    "page": page,
                    "page_size": page_size,
                    "total_books": total_books,
                    "total_pages": total_pages,
                }
            )
        except Exception as exc:
            logger.exception("Error in catalogue: %s", exc)
            return _error(str(exc))

    async def handle_search(self, request: Request) -> JSONResponse:
        """GET /bookshelf/search — Search books by title or author."""
        try:
            query = request.query_params.get("query", "").lower()
            field = request.query_params.get("field", "title")

            if not query:
                return _error("query parameter is required")

            if field not in ["title", "author"]:
                return _error("field must be 'title' or 'author'")

            books = self._list_all_books()
            filtered = [b for b in books if query in str(b.get(field, "")).lower()]

            return _ok(
                {"books": filtered, "total_results": len(filtered), "query": query, "field": field}
            )
        except Exception as exc:
            logger.exception("Error in search: %s", exc)
            return _error(str(exc))
