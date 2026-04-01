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

Environment variables
---------------------
BEDROCK_MODEL_ID       Bedrock model ID (required)
BEDROCK_REGION         AWS region for Bedrock calls (default: eu-west-2)
LANDING_BUCKET         S3 bucket name for uploads (required)
RAW_BUCKET             S3 bucket name for accepted metadata JSON (required)
CORS_ALLOWED_ORIGINS   Comma-separated allowed CORS origins (default: http://localhost:5173)
"""

import logging
import os

from accept_handler import AcceptHandler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from metadata_initial_handler import MetadataInitialHandler
from metadata_refine_handler import MetadataRefineHandler
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

_presigned = PresignedUrlHandler()
_initial = MetadataInitialHandler()
_refine = MetadataRefineHandler()
_accept = AcceptHandler()


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/api/upload/presigned")
async def get_presigned_url(request: Request):
    return await _presigned.handle(request)


@app.post("/api/metadata/initial")
async def metadata_initial(request: Request):
    return await _initial.handle(request)


@app.post("/api/metadata/refine")
async def metadata_refine(request: Request):
    return await _refine.handle(request)


@app.post("/api/metadata/accept")
async def metadata_accept(request: Request):
    return await _accept.handle(request)
