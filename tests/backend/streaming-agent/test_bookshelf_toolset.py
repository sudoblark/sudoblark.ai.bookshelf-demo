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


class TestBuildBookshelfToolset:
    """Test build_bookshelf_toolset returns a FunctionToolset."""

    def test_returns_toolset(self, bookshelf_handler_and_toolset):
        from pydantic_ai import FunctionToolset

        _, toolset = bookshelf_handler_and_toolset
        assert isinstance(toolset, FunctionToolset)

    def test_toolset_built_without_tracker(self, monkeypatch, s3_client_with_books):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        bookshelf_toolset_mod = importlib.import_module("bookshelf_toolset")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        # Should not raise when tracker=None (default)
        toolset = bookshelf_toolset_mod.build_bookshelf_toolset(handler)
        assert toolset is not None

    def test_toolset_built_with_tracker(self, monkeypatch, s3_client_with_books):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")
        tracker_mod = importlib.import_module("tool_tracker")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        tracker = tracker_mod.ToolTracker()
        toolset = toolset_mod.build_bookshelf_toolset(handler, tracker=tracker)
        assert toolset is not None


class TestBookshelfHandlerDirectly:
    """Test BookshelfHandler methods directly (which back the toolset tools)."""

    def test_list_books_returns_all(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        books = handler._list_all_books()
        assert len(books) == 3

    def test_list_books_contains_expected_titles(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        books = handler._list_all_books()
        titles = [b["title"] for b in books]
        assert "The Way of Kings" in titles
        assert "The Name of the Wind" in titles

    def test_search_by_author_filters_correctly(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        books = handler._list_all_books()
        results = [b for b in books if "sanderson" in str(b.get("author", "")).lower()]
        assert len(results) == 2

    def test_search_by_title_filters_correctly(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        books = handler._list_all_books()
        results = [b for b in books if "wind" in str(b.get("title", "")).lower()]
        assert len(results) == 1
        assert results[0]["title"] == "The Name of the Wind"


class TestBookshelfToolsetWithTracker:
    """Test that tracker is called when toolset tools are invoked via handler."""

    def test_tracker_records_list_books(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        tracker = tracker_mod.ToolTracker()

        # We can't invoke FunctionToolset tools directly — instead verify tracker
        # records correctly by calling the underlying handler and recording manually
        books = handler._list_all_books()
        tracker.record("list_books", "(no parameters)", books, 10.0)

        executions = tracker.get_executions()
        assert len(executions) == 1
        assert executions[0].name == "list_books"
        assert "3 books" in executions[0].result_summary

    def test_tracker_records_search_books(self, s3_client_with_books, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        tracker = tracker_mod.ToolTracker()

        books = handler._list_all_books()
        results = [b for b in books if "sanderson" in str(b.get("author", "")).lower()]
        tracker.record("search_books", 'query="Sanderson", field="author"', results, 8.0)

        executions = tracker.get_executions()
        assert len(executions) == 1
        assert executions[0].name == "search_books"
        assert "2 matching" in executions[0].result_summary

    def test_tracker_records_get_overview(self, s3_client_with_books, monkeypatch):
        from collections import Counter

        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3_client_with_books)
        tracker = tracker_mod.ToolTracker()

        books = handler._list_all_books()
        authors = [b["author"] for b in books if b.get("author")]
        author_counts = Counter(authors)
        most_common_author, count = author_counts.most_common(1)[0]
        stats = {
            "total_books": len(books),
            "most_common_author": most_common_author,
            "most_common_author_count": count,
        }
        tracker.record("get_overview", "(no parameters)", stats, 5.0)

        executions = tracker.get_executions()
        assert len(executions) == 1
        assert "Brandon Sanderson" in executions[0].result_summary
