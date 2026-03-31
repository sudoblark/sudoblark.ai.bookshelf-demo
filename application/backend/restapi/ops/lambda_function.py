"""Ops dashboard Lambda handler.

Serves two read-only endpoints backed by the ingestion-tracking DynamoDB table:

    GET /ops/files             — list all tracked files (Scan)
    GET /ops/files/{file_id}   — detail for a single file (GetItem)

Routing is determined by the presence of ``pathParameters.file_id`` in the
API Gateway event.
"""

import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import boto3
from common.tracker import BookshelfTracker

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _serialise(obj: Any) -> str:
    """JSON default serialiser — converts Decimal to string."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _ok(body: Dict) -> Dict:
    return {
        "statusCode": 200,
        "headers": _CORS_HEADERS,
        "body": json.dumps(body, default=_serialise),
    }


def _not_found(message: str) -> Dict:
    return {
        "statusCode": 404,
        "headers": _CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


def _error(message: str) -> Dict:
    return {
        "statusCode": 500,
        "headers": _CORS_HEADERS,
        "body": json.dumps({"error": message}),
    }


class OpsHandler:
    """REST handler for the ops dashboard endpoints."""

    def __init__(self, dynamodb_resource: Optional[Any] = None) -> None:
        self._tracker = BookshelfTracker(
            dynamodb_resource=dynamodb_resource or boto3.resource("dynamodb"),
            table_name=os.environ["TRACKING_TABLE"],
        )

    def __call__(self, event: Dict, context: Any = None) -> Dict:
        try:
            file_id = (event.get("pathParameters") or {}).get("file_id")
            if file_id:
                return self._get_file(file_id)
            return self._list_files()
        except Exception as exc:
            return _error(str(exc))

    def _list_files(self) -> Dict:
        files = self._tracker.list_all()
        return _ok({"files": files, "count": len(files)})

    def _get_file(self, file_id: str) -> Dict:
        record = self._tracker.get_by_id(file_id)
        if record is None:
            return _not_found(f"File '{file_id}' not found")
        return _ok({"file": record})


handler_instance = OpsHandler()


def handler(event: Dict, context: Any = None) -> Dict:
    return handler_instance(event, context)
