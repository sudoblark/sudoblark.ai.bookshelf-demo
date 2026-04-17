"""Tests for bookshelf toolset."""

import importlib
import json
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Setup path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent / "application/backend/streaming-agent"),
)

RAW_BUCKET = "test-raw-bucket"

SAMPLE_BOOKS = [
    {
        "upload_id": "book-001",
        "title": "The Way of Kings",
        "author": "Brandon Sanderson",
        "isbn": "9780765326355",
        "published_year": 2010,
    },
    {
        "upload_id": "book-002",
        "title": "Words of Radiance",
        "author": "Brandon Sanderson",
        "isbn": "9780765326362",
        "published_year": 2014,
    },
    {
        "upload_id": "book-003",
        "title": "The Name of the Wind",
        "author": "Patrick Rothfuss",
        "isbn": "9780756404079",
        "published_year": 2007,
    },
]


@pytest.fixture
def s3_client_with_books(aws_credentials, monkeypatch):
    """Create S3 client and seed with sample books."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)

    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-2")
        client.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        for book in SAMPLE_BOOKS:
            author = book["author"].replace(" ", "_")
            year = book["published_year"]
            key = f"author={author}/published_year={year}/{book['upload_id']}.json"
            client.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode("utf-8"))

        yield client


@pytest.fixture
def bookshelf_handler_and_toolset(s3_client_with_books, monkeypatch):
    """Create bookshelf handler and toolset with mocked S3."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)

    bookshelf_mod = importlib.import_module("bookshelf_handler")
    toolset_mod = importlib.import_module("bookshelf_toolset")

    handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
    toolset = toolset_mod.build_bookshelf_toolset(handler)

    return handler, toolset
