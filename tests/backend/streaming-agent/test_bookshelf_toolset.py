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


def test_list_books_tool(bookshelf_handler_and_toolset):
    """Test list_books tool returns all books."""
    handler, toolset = bookshelf_handler_and_toolset

    books = toolset.list_books()

    assert len(books) == 3
    assert books[0]["title"] == "The Way of Kings"
    assert books[1]["author"] == "Brandon Sanderson"
    assert books[2]["title"] == "The Name of the Wind"


def test_search_books_by_author(bookshelf_handler_and_toolset):
    """Test search_books tool with author field."""
    handler, toolset = bookshelf_handler_and_toolset

    results = toolset.search_books("sanderson", "author")

    assert len(results) == 2
    assert all("Sanderson" in b["author"] for b in results)


def test_search_books_by_title(bookshelf_handler_and_toolset):
    """Test search_books tool with title field."""
    handler, toolset = bookshelf_handler_and_toolset

    results = toolset.search_books("way", "title")

    assert len(results) == 1
    assert results[0]["title"] == "The Way of Kings"


def test_search_books_no_results(bookshelf_handler_and_toolset):
    """Test search_books returns empty list for no matches."""
    handler, toolset = bookshelf_handler_and_toolset

    results = toolset.search_books("nonexistent", "title")

    assert results == []


def test_search_books_case_insensitive(bookshelf_handler_and_toolset):
    """Test search is case-insensitive."""
    handler, toolset = bookshelf_handler_and_toolset

    results = toolset.search_books("SANDERSON", "author")

    assert len(results) == 2


def test_search_books_invalid_field_defaults_to_title(bookshelf_handler_and_toolset):
    """Test search with invalid field defaults to title."""
    handler, toolset = bookshelf_handler_and_toolset

    results = toolset.search_books("way", "invalid_field")

    # Should default to title search and find 1 result
    assert len(results) == 1
    assert results[0]["title"] == "The Way of Kings"


def test_get_overview(bookshelf_handler_and_toolset):
    """Test get_overview tool returns correct stats."""
    handler, toolset = bookshelf_handler_and_toolset

    stats = toolset.get_overview()

    assert stats["total_books"] == 3
    assert stats["most_common_author"] == "Brandon Sanderson"
    assert stats["most_common_author_count"] == 2


def test_get_overview_empty_bookshelf(monkeypatch):
    """Test get_overview with no books."""
    with mock_aws():
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)

        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3)
        toolset = toolset_mod.build_bookshelf_toolset(handler)

        stats = toolset.get_overview()

        assert stats["total_books"] == 0
        assert stats["most_common_author"] is None
        assert stats["most_common_author_count"] == 0


def test_list_books_empty_bucket(monkeypatch):
    """Test list_books with empty bucket."""
    with mock_aws():
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)

        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3)
        toolset = toolset_mod.build_bookshelf_toolset(handler)

        books = toolset.list_books()

        assert books == []
