"""Handler for bookshelf display endpoints.

Queries the DynamoDB tracking table as the single source of truth for book records.
See docs/adr/0005-upload-pipeline-stages.md for architectural rationale.

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
import numpy as np
from common.tracker import BookshelfTracker, UploadStage
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

    def __init__(
        self, s3_client: Optional[Any] = None, dynamodb_resource: Optional[Any] = None
    ) -> None:
        self._s3 = s3_client or boto3.client("s3")
        self._raw_bucket = os.environ["RAW_BUCKET"]
        self._processed_bucket = os.environ.get("PROCESSED_BUCKET", "")
        self._tracker = BookshelfTracker(
            dynamodb_resource=dynamodb_resource,
            table_name=os.environ.get("TRACKING_TABLE", ""),
        )

    def _list_all_books(self) -> List[Dict]:
        """Return all books with a completed analysed stage, using DynamoDB as source of truth.

        Fetches tracking records with an analysed stage entry, then reads the
        metadata JSON from S3. Prefers the processed bucket key if available,
        falls back to the raw bucket key for records that have not yet been copied.

        Returns:
            List of book dicts, each with 'book_id' and 's3_key' added.
        """
        books = []
        try:
            records = self._tracker.list_all()
        except Exception as e:
            logger.exception("Error reading tracking table for books: %s", e)
            raise

        for record in records:
            upload_id = record.get("upload_id", "")
            if not upload_id:
                continue

            stages = record.get("stages") or {}
            analysed = stages.get(UploadStage.ANALYSED.value) or {}
            if not analysed:
                continue

            # Prefer processed key; fall back to raw if not yet copied
            processed = stages.get(UploadStage.PROCESSED.value) or {}
            if processed.get("destinationKey") and self._processed_bucket:
                bucket = self._processed_bucket
                key = processed["destinationKey"]
            else:
                bucket = analysed.get("destinationBucket") or self._raw_bucket
                key = analysed.get("destinationKey", "")

            if not key:
                continue

            try:
                response = self._s3.get_object(Bucket=bucket, Key=key)
                data = json.loads(response["Body"].read())
                data["s3_key"] = key
                data["book_id"] = data.get("upload_id", upload_id)
                books.append(data)
            except Exception as e:
                logger.warning("Failed to fetch book metadata %s/%s: %s", bucket, key, e)

        return books

    def _list_all_embeddings(self) -> Dict[str, List[float]]:
        """Fetch embeddings for all uploads with a completed embedding stage.

        Uses the tracker to find records with a completed EMBEDDING stage, then
        fetches each embedding file directly using the stored destinationBucket
        and destinationKey — no bucket scan needed.
        """
        embeddings: Dict[str, List[float]] = {}
        try:
            records = self._tracker.list_all()
        except Exception as e:
            logger.exception("Error reading tracking table for embeddings: %s", e)
            return embeddings

        for record in records:
            upload_id = record.get("upload_id", "")
            if not upload_id:
                continue

            stages = record.get("stages") or {}
            embedding_stage = stages.get(UploadStage.EMBEDDING.value) or {}
            embedding_key = embedding_stage.get("destinationKey")
            embedding_bucket = embedding_stage.get("destinationBucket") or self._processed_bucket

            if not embedding_key:
                continue

            try:
                response = self._s3.get_object(Bucket=embedding_bucket, Key=embedding_key)
                data = json.loads(response["Body"].read())
                if "embedding" in data:
                    embeddings[upload_id] = data["embedding"]
            except Exception as e:
                logger.debug("No embedding at %s/%s: %s", embedding_bucket, embedding_key, e)

        return embeddings

    def _compute_related(self, file_id: str, limit: int) -> List[Dict]:
        """Return the top-N most similar books to file_id by cosine similarity."""
        all_embeddings = self._list_all_embeddings()
        if file_id not in all_embeddings:
            return []

        target = np.array(all_embeddings[file_id], dtype=float)
        target_norm = float(np.linalg.norm(target))

        book_by_id = {b.get("book_id", b.get("upload_id", "")): b for b in self._list_all_books()}

        scored = []
        for uid, emb in all_embeddings.items():
            if uid == file_id:
                continue
            vec = np.array(emb, dtype=float)
            norm = float(np.linalg.norm(vec))
            if target_norm == 0 or norm == 0:
                continue
            similarity = float(np.dot(target, vec) / (target_norm * norm))
            book = book_by_id.get(uid)
            if book:
                scored.append(
                    {
                        "file_id": uid,
                        "title": book.get("title", ""),
                        "author": book.get("author", ""),
                        "similarity": round(similarity, 4),
                        "s3_key": book.get("s3_key", ""),
                    }
                )

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    def _compute_graph(self, threshold: float) -> Dict:
        """Return all-pairs cosine similarity as a graph (nodes + edges above threshold)."""
        all_embeddings = self._list_all_embeddings()
        book_by_id = {b.get("book_id", b.get("upload_id", "")): b for b in self._list_all_books()}

        nodes = []
        for uid in all_embeddings:
            book = book_by_id.get(uid)
            if book:
                nodes.append(
                    {
                        "id": uid,
                        "title": book.get("title", ""),
                        "author": book.get("author", ""),
                    }
                )

        ids = list(all_embeddings.keys())
        edges = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                va = np.array(all_embeddings[a], dtype=float)
                vb = np.array(all_embeddings[b], dtype=float)
                na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
                if na == 0 or nb == 0:
                    continue
                sim = float(np.dot(va, vb) / (na * nb))
                if sim >= threshold:
                    edges.append({"source": a, "target": b, "weight": round(sim, 4)})

        return {"nodes": nodes, "edges": edges, "threshold": threshold}

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

    async def handle_related(self, request: Request, file_id: str) -> JSONResponse:
        """GET /bookshelf/{file_id}/related — Return top-N similar books."""
        try:
            limit = min(int(request.query_params.get("limit", 5)), 20)
            related = self._compute_related(file_id, limit)
            return _ok({"file_id": file_id, "related": related})
        except Exception as exc:
            logger.exception("Error in related: %s", exc)
            return _error(str(exc))

    async def handle_similarity_graph(self, request: Request) -> JSONResponse:
        """GET /bookshelf/graph — Return all-pairs similarity as a graph."""
        try:
            threshold = float(request.query_params.get("threshold", 0.5))
            graph = self._compute_graph(threshold)
            return _ok(graph)
        except Exception as exc:
            logger.exception("Error in similarity_graph: %s", exc)
            return _error(str(exc))
