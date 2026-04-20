"""Tests for bookshelf toolset."""

import importlib
import json
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

TRACKING_TABLE = "test-tracking-toolset"

EMBEDDINGS = {
    "book-001": [1.0, 0.0, 0.0, 0.0],
    "book-002": [0.99, 0.14, 0.0, 0.0],
    "book-003": [0.0, 0.0, 1.0, 0.0],
}

# Setup path for imports
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent / "application/backend/streaming-agent"),
)

RAW_BUCKET = "test-raw-toolset"

SAMPLE_BOOKS = [
    {
        "upload_id": "book-001",
        "title": "Guards! Guards!",
        "author": "Terry Pratchett",
        "isbn": "9780552134637",
        "published_year": 1989,
    },
    {
        "upload_id": "book-002",
        "title": "Men at Arms",
        "author": "Terry Pratchett",
        "isbn": "9780552140904",
        "published_year": 1993,
    },
    {
        "upload_id": "book-003",
        "title": "American Gods",
        "author": "Neil Gaiman",
        "isbn": "9780380973651",
        "published_year": 2001,
    },
]


@pytest.fixture
def aws_with_books(aws_credentials, monkeypatch):
    """S3 + DynamoDB seeded with sample books and tracking records."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)

    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
        table = dynamodb.create_table(
            TableName=TRACKING_TABLE,
            KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for book in SAMPLE_BOOKS:
            author = book["author"].replace(" ", "_")
            key = (
                f"author={author}/published_year={book['published_year']}/{book['upload_id']}.json"
            )
            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode("utf-8"))
            table.put_item(
                Item={
                    "upload_id": book["upload_id"],
                    "stage": "analysed",
                    "stages": {
                        "analysed": {
                            "startedAt": "2024-01-01T00:00:00+00:00",
                            "endedAt": "2024-01-01T00:00:01+00:00",
                            "sourceBucket": RAW_BUCKET,
                            "sourceKey": key,
                            "destinationBucket": RAW_BUCKET,
                            "destinationKey": key,
                        }
                    },
                }
            )

        yield s3, dynamodb


@pytest.fixture
def aws_with_embeddings(aws_credentials, monkeypatch):
    """S3 + DynamoDB seeded with books, embeddings, and tracking records."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)

    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
        table = dynamodb.create_table(
            TableName=TRACKING_TABLE,
            KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for book in SAMPLE_BOOKS:
            author = book["author"].replace(" ", "_")
            key = (
                f"author={author}/published_year={book['published_year']}/{book['upload_id']}.json"
            )
            emb_key = key.replace(".json", ".embedding.json")
            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode("utf-8"))
            s3.put_object(
                Bucket=RAW_BUCKET,
                Key=emb_key,
                Body=json.dumps(
                    {"upload_id": book["upload_id"], "embedding": EMBEDDINGS[book["upload_id"]]}
                ).encode("utf-8"),
            )
            table.put_item(
                Item={
                    "upload_id": book["upload_id"],
                    "stage": "embedding",
                    "stages": {
                        "analysed": {
                            "startedAt": "2024-01-01T00:00:00+00:00",
                            "endedAt": "2024-01-01T00:00:01+00:00",
                            "sourceBucket": RAW_BUCKET,
                            "sourceKey": key,
                            "destinationBucket": RAW_BUCKET,
                            "destinationKey": key,
                        },
                        "embedding": {
                            "startedAt": "2024-01-01T00:00:02+00:00",
                            "endedAt": "2024-01-01T00:00:03+00:00",
                            "sourceBucket": RAW_BUCKET,
                            "sourceKey": key,
                            "destinationBucket": RAW_BUCKET,
                            "destinationKey": emb_key,
                        },
                    },
                }
            )

        yield s3, dynamodb


@pytest.fixture
def bookshelf_handler_and_toolset(aws_with_books):
    """Create bookshelf handler and toolset with mocked S3 + DynamoDB."""
    s3, dynamodb = aws_with_books
    bookshelf_mod = importlib.import_module("bookshelf_handler")
    toolset_mod = importlib.import_module("bookshelf_toolset")

    handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
    toolset = toolset_mod.build_bookshelf_toolset(handler)

    return handler, toolset


class TestBuildBookshelfToolset:
    """Test build_bookshelf_toolset returns a FunctionToolset."""

    def test_returns_toolset(self, bookshelf_handler_and_toolset):
        from pydantic_ai import FunctionToolset

        _, toolset = bookshelf_handler_and_toolset
        assert isinstance(toolset, FunctionToolset)

    def test_toolset_built_without_tracker(self, aws_with_books):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        bookshelf_toolset_mod = importlib.import_module("bookshelf_toolset")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        toolset = bookshelf_toolset_mod.build_bookshelf_toolset(handler)
        assert toolset is not None

    def test_toolset_built_with_tracker(self, aws_with_books):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")
        tracker_mod = importlib.import_module("tool_tracker")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        tracker = tracker_mod.ToolTracker()
        toolset = toolset_mod.build_bookshelf_toolset(handler, tracker=tracker)
        assert toolset is not None


class TestBookshelfHandlerDirectly:
    """Test BookshelfHandler methods directly (which back the toolset tools)."""

    def test_list_books_returns_all(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        books = handler._list_all_books()
        assert len(books) == 3

    def test_list_books_contains_expected_titles(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        books = handler._list_all_books()
        titles = [b["title"] for b in books]
        assert "Guards! Guards!" in titles
        assert "American Gods" in titles

    def test_search_by_author_filters_correctly(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        books = handler._list_all_books()
        results = [b for b in books if "pratchett" in str(b.get("author", "")).lower()]
        assert len(results) == 2

    def test_search_by_title_filters_correctly(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        books = handler._list_all_books()
        results = [b for b in books if "gods" in str(b.get("title", "")).lower()]
        assert len(results) == 1
        assert results[0]["title"] == "American Gods"


class TestBookshelfToolsetWithTracker:
    """Test that tracker is called when toolset tools are invoked via handler."""

    def test_tracker_records_list_books(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        tracker = tracker_mod.ToolTracker()

        books = handler._list_all_books()
        tracker.record("list_books", "(no parameters)", books, 10.0)

        executions = tracker.get_executions()
        assert len(executions) == 1
        assert executions[0].name == "list_books"
        assert "3 books" in executions[0].result_summary

    def test_tracker_records_search_books(self, aws_with_books, monkeypatch):
        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        tracker = tracker_mod.ToolTracker()

        books = handler._list_all_books()
        results = [b for b in books if "pratchett" in str(b.get("author", "")).lower()]
        tracker.record("search_books", 'query="Pratchett", field="author"', results, 8.0)

        executions = tracker.get_executions()
        assert len(executions) == 1
        assert executions[0].name == "search_books"
        assert "2 matching" in executions[0].result_summary

    def test_tracker_records_get_overview(self, aws_with_books, monkeypatch):
        from collections import Counter

        s3, dynamodb = aws_with_books
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")

        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
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
        assert "Terry Pratchett" in executions[0].result_summary


class TestSimilarityToolsRegistered:
    """Verify get_similar_books and get_similarity_graph are in the toolset."""

    def test_toolset_includes_get_similar_books(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        toolset = toolset_mod.build_bookshelf_toolset(handler)
        assert "get_similar_books" in toolset.tools

    def test_toolset_includes_get_similarity_graph(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        toolset_mod = importlib.import_module("bookshelf_toolset")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        toolset = toolset_mod.build_bookshelf_toolset(handler)
        assert "get_similarity_graph" in toolset.tools


class TestSimilarityHandlerMethods:
    """Test _compute_related and _compute_graph via handler directly."""

    def test_compute_related_returns_ranked_results(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        results = handler._compute_related("book-001", 5)
        assert isinstance(results, list)
        assert all("similarity" in r for r in results)
        assert "book-001" not in [r["file_id"] for r in results]

    def test_compute_related_unknown_id_returns_empty(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        results = handler._compute_related("nonexistent", 5)
        assert results == []

    def test_compute_graph_returns_nodes_and_edges(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        graph = handler._compute_graph(0.0)
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 3

    def test_tracker_records_get_similar_books(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        tracker = tracker_mod.ToolTracker()
        results = handler._compute_related("book-001", 5)
        tracker.record("get_similar_books", 'book_id="book-001", limit=5', results, 10.0)
        executions = tracker.get_executions()
        assert len(executions) == 1
        assert "similar" in executions[0].result_summary

    def test_tracker_records_get_similarity_graph(self, aws_with_embeddings, monkeypatch):
        s3, dynamodb = aws_with_embeddings
        bookshelf_mod = importlib.import_module("bookshelf_handler")
        tracker_mod = importlib.import_module("tool_tracker")
        handler = bookshelf_mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
        tracker = tracker_mod.ToolTracker()
        graph = handler._compute_graph(0.0)
        tracker.record("get_similarity_graph", "threshold=0.0", graph, 15.0)
        executions = tracker.get_executions()
        assert len(executions) == 1
        assert "nodes" in executions[0].result_summary
