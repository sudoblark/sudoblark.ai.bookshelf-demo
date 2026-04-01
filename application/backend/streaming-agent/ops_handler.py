"""Handler for GET /ops/files and GET /ops/files/{file_id} dashboard endpoints.

Provides read-only access to the ingestion-tracking DynamoDB table for monitoring
file upload progress through the pipeline.

Endpoints
---------
GET /ops/files
    List all tracked files (Scan with 100-item limit).
    Response: {"files": [...], "count": N}

GET /ops/files/{file_id}
    Get detail for a single file (GetItem).
    Response: {"file": {...}}
    404 if file_id not found.
"""

import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from common.tracker import BookshelfTracker
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _serialise(obj: Any) -> str:
    """JSON default serialiser — converts Decimal to string."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _ok(body: Dict) -> JSONResponse:
    return JSONResponse(body, status_code=200, headers=_CORS_HEADERS)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=404, headers=_CORS_HEADERS)


def _error(message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=500, headers=_CORS_HEADERS)


class OpsHandler:
    """REST handler for the ops dashboard endpoints."""

    def __init__(self, dynamodb_resource: Optional[Any] = None) -> None:
        self._tracker = BookshelfTracker(
            dynamodb_resource=dynamodb_resource or boto3.resource("dynamodb"),
            table_name=os.environ["TRACKING_TABLE"],
        )

    async def handle_list(self, request: Request) -> JSONResponse:
        """Return all tracked files."""
        try:
            files = self._tracker.list_all()
            response = {"files": files, "count": len(files)}
            # Serialize Decimal types to strings for JSON
            return _ok(json.loads(json.dumps(response, default=_serialise)))
        except Exception as exc:
            logger.exception("Error listing files: %s", exc)
            return _error(str(exc))

    async def handle_get(self, request: Request, file_id: str) -> JSONResponse:
        """Return a single tracked file by ID."""
        try:
            record = self._tracker.get_by_id(file_id)
            if record is None:
                return _not_found(f"File '{file_id}' not found")
            # Serialize Decimal types to strings for JSON
            response = {"file": record}
            return _ok(json.loads(json.dumps(response, default=_serialise)))
        except Exception as exc:
            logger.exception("Error getting file %s: %s", file_id, exc)
            return _error(str(exc))
