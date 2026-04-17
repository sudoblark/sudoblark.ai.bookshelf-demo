"""FastAPI streaming agent service for the bookshelf demo.

Endpoints
---------
GET  /health
    Container health check — always returns 200.

GET  /api/upload/presigned
    Generate a pre-signed S3 PUT URL for direct browser-to-S3 upload.
    Query param: ``filename`` (required).

POST /api/metadata/initial
    One-shot cold extraction of book metadata from an uploaded cover image.
    Streams SSE — see ``metadata_initial_handler.py``.

POST /api/metadata/refine
    Multi-turn refinement conversation.  History is kept in process memory,
    keyed by the ``session_id`` returned from ``/api/upload/presigned``.
    Streams SSE — see ``metadata_refine_handler.py``.

POST /api/metadata/accept
    Save the confirmed metadata as JSON to the raw S3 bucket with Hive-style
    partitioning (``author={}/published_year={}/``).

GET  /api/ops/files
    List all tracked file uploads from the ingestion tracking table.

GET  /api/ops/files/{file_id}
    Get detailed tracking information for a specific upload by ID.

GET  /api/bookshelf/overview
    High-level bookshelf stats: total count, most common author.

GET  /api/bookshelf/catalogue
    Paginated list of books (5 per page by default).
    Query params: page (1-indexed), page_size (max 20).

GET  /api/bookshelf/search
    Search books by title or author.
    Query params: query (required), field (title|author).

POST /api/ook/chat
    General AI chat interface for exploring the user's bookshelf.
    Request: {session_id: str, message: str}
    Streams SSE — see ``ook_handler.py``.

Environment variables
---------------------
BEDROCK_MODEL_ID       Bedrock model ID (required)
BEDROCK_REGION         AWS region for Bedrock calls (default: eu-west-2)
LANDING_BUCKET         S3 bucket name for uploads (required)
RAW_BUCKET             S3 bucket name for accepted metadata JSON (required)
TRACKING_TABLE         DynamoDB table name for ingestion tracking (required)
CORS_ALLOWED_ORIGINS   Comma-separated allowed CORS origins (default: http://localhost:5173)
"""

import logging
import os

import boto3
from accept_handler import AcceptHandler
from bookshelf_handler import BookshelfHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from metadata_initial_handler import MetadataInitialHandler
from metadata_refine_handler import MetadataRefineHandler
from ook_handler import OokHandler
from ops_handler import OpsHandler
from presigned_handler import PresignedUrlHandler

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="Bookshelf Streaming Agent")

_allowed_origins = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_dynamodb = boto3.resource("dynamodb")

_presigned = PresignedUrlHandler()
_initial = MetadataInitialHandler(dynamodb_resource=_dynamodb)
_refine = MetadataRefineHandler()
_accept = AcceptHandler(dynamodb_resource=_dynamodb)
_ops = OpsHandler()
_bookshelf = BookshelfHandler()
_ook = OokHandler()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/api/upload/presigned")
async def get_presigned_url(request: Request) -> JSONResponse:
    return await _presigned.handle(request)


@app.post("/api/metadata/initial")
async def metadata_initial(request: Request) -> StreamingResponse:
    return await _initial.handle(request)


@app.post("/api/metadata/refine")
async def metadata_refine(request: Request) -> StreamingResponse:
    return await _refine.handle(request)


@app.post("/api/metadata/accept")
async def metadata_accept(request: Request) -> JSONResponse:
    return await _accept.handle(request)


@app.get("/api/ops/files")
async def ops_list_files(request: Request) -> JSONResponse:
    return await _ops.handle_list(request)


@app.get("/api/ops/files/{file_id}")
async def ops_get_file(request: Request, file_id: str) -> JSONResponse:
    return await _ops.handle_get(request, file_id)


@app.get("/api/bookshelf/overview")
async def bookshelf_overview(request: Request) -> JSONResponse:
    return await _bookshelf.handle_overview(request)


@app.get("/api/bookshelf/catalogue")
async def bookshelf_catalogue(request: Request) -> JSONResponse:
    return await _bookshelf.handle_catalogue(request)


@app.get("/api/bookshelf/search")
async def bookshelf_search(request: Request) -> JSONResponse:
    return await _bookshelf.handle_search(request)


@app.post("/api/ook/chat")
async def ook_chat(request: Request) -> StreamingResponse:
    return await _ook.handle(request)
