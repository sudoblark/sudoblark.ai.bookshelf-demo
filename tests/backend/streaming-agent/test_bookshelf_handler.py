"""Tests for BookshelfHandler (overview, catalogue, search)."""

import importlib
import json
import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)

RAW_BUCKET = "test-raw-handler"
TRACKING_TABLE = "test-tracking-handler"

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
        "title": "Small Gods",
        "author": "Terry Pratchett",
        "isbn": "9780552140225",
        "published_year": 1992,
    },
    {
        "upload_id": "book-003",
        "title": "American Gods",
        "author": "Neil Gaiman",
        "isbn": "9780380973651",
        "published_year": 2001,
    },
]


def _book_key(book: dict) -> str:
    author = book["author"].replace(" ", "_")
    return f"author={author}/published_year={book['published_year']}/{book['upload_id']}.json"


@pytest.fixture
def aws_with_books(aws_credentials, monkeypatch):
    """S3 + DynamoDB seeded with three books and tracking records."""
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
            key = _book_key(book)
            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode())
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
def handler(aws_with_books):
    s3, dynamodb = aws_with_books
    mod = importlib.import_module("bookshelf_handler")
    return mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)


@pytest.fixture
def empty_handler(aws_credentials, monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-west-2")
        s3.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
        dynamodb.create_table(
            TableName=TRACKING_TABLE,
            KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        mod = importlib.import_module("bookshelf_handler")
        yield mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)


def _make_request(params: dict = None):
    req = MagicMock()
    req.query_params = params or {}
    return req


class TestListAllBooks:
    """Test BookshelfHandler._list_all_books()."""

    def test_returns_all_books(self, handler):
        books = handler._list_all_books()
        assert len(books) == 3

    def test_books_have_s3_key(self, handler):
        books = handler._list_all_books()
        assert all("s3_key" in b for b in books)

    def test_books_have_book_id(self, handler):
        books = handler._list_all_books()
        assert all("book_id" in b for b in books)

    def test_empty_table_returns_empty_list(self, empty_handler):
        books = empty_handler._list_all_books()
        assert books == []

    def test_record_without_analysed_stage_excluded(self, aws_credentials, monkeypatch):
        """Records with no analysed stage entry are not returned."""
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
            # Record exists but has no analysed stage
            table.put_item(Item={"upload_id": "book-001", "stage": "queued", "stages": {}})
            mod = importlib.import_module("bookshelf_handler")
            h = mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
            books = h._list_all_books()
            assert books == []

    def test_only_analysed_records_returned(self, aws_credentials, monkeypatch):
        """Only records with an analysed stage are returned; queued records are excluded."""
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
            key = "author=Terry_Pratchett/published_year=1989/book-001.json"
            s3.put_object(
                Bucket=RAW_BUCKET,
                Key=key,
                Body=json.dumps({"title": "Guards! Guards!", "upload_id": "book-001"}).encode(),
            )
            # One analysed, one queued
            table.put_item(
                Item={
                    "upload_id": "book-001",
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
            table.put_item(Item={"upload_id": "book-002", "stage": "queued", "stages": {}})
            mod = importlib.import_module("bookshelf_handler")
            h = mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
            books = h._list_all_books()
            assert len(books) == 1
            assert books[0]["title"] == "Guards! Guards!"


class TestHandleOverview:
    """Test BookshelfHandler.handle_overview()."""

    @pytest.mark.asyncio
    async def test_returns_200(self, handler):
        resp = await handler.handle_overview(_make_request())
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_total_books_correct(self, handler):
        resp = await handler.handle_overview(_make_request())
        data = json.loads(resp.body)
        assert data["total_books"] == 3

    @pytest.mark.asyncio
    async def test_most_common_author(self, handler):
        resp = await handler.handle_overview(_make_request())
        data = json.loads(resp.body)
        assert data["most_common_author"] == "Terry Pratchett"
        assert data["most_common_author_count"] == 2

    @pytest.mark.asyncio
    async def test_empty_table_returns_zero_stats(self, empty_handler):
        resp = await empty_handler.handle_overview(_make_request())
        data = json.loads(resp.body)
        assert data["total_books"] == 0
        assert data["most_common_author"] is None
        assert data["most_common_author_count"] == 0


class TestHandleCatalogue:
    """Test BookshelfHandler.handle_catalogue()."""

    @pytest.mark.asyncio
    async def test_returns_200(self, handler):
        resp = await handler.handle_catalogue(_make_request({"page": "1", "page_size": "5"}))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_default_page_size(self, handler):
        resp = await handler.handle_catalogue(_make_request())
        data = json.loads(resp.body)
        assert data["page_size"] == 5

    @pytest.mark.asyncio
    async def test_page_size_capped_at_20(self, handler):
        resp = await handler.handle_catalogue(_make_request({"page_size": "100"}))
        data = json.loads(resp.body)
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_total_books_in_response(self, handler):
        resp = await handler.handle_catalogue(_make_request())
        data = json.loads(resp.body)
        assert data["total_books"] == 3

    @pytest.mark.asyncio
    async def test_books_list_in_response(self, handler):
        resp = await handler.handle_catalogue(_make_request())
        data = json.loads(resp.body)
        assert "books" in data
        assert len(data["books"]) == 3

    @pytest.mark.asyncio
    async def test_pagination_second_page(self, handler):
        resp = await handler.handle_catalogue(_make_request({"page": "2", "page_size": "2"}))
        data = json.loads(resp.body)
        assert data["page"] == 2
        assert len(data["books"]) == 1  # 3 books, page 2 of 2


class TestHandleSearch:
    """Test BookshelfHandler.handle_search()."""

    @pytest.mark.asyncio
    async def test_search_by_author(self, handler):
        resp = await handler.handle_search(_make_request({"query": "Pratchett", "field": "author"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 2

    @pytest.mark.asyncio
    async def test_search_by_title(self, handler):
        resp = await handler.handle_search(_make_request({"query": "gods", "field": "title"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 2  # Small Gods + American Gods

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, handler):
        resp = await handler.handle_search(_make_request({"query": "pratchett", "field": "author"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 2

    @pytest.mark.asyncio
    async def test_search_no_query_returns_error(self, handler):
        resp = await handler.handle_search(_make_request({"field": "title"}))
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_search_invalid_field_returns_error(self, handler):
        resp = await handler.handle_search(_make_request({"query": "test", "field": "isbn"}))
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_search_no_results(self, handler):
        resp = await handler.handle_search(_make_request({"query": "zzznomatch", "field": "title"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 0


class TestCorsHeaders:
    """Test CORS headers are present on all responses."""

    @pytest.mark.asyncio
    async def test_cors_headers_on_overview(self, handler):
        resp = await handler.handle_overview(_make_request())
        assert resp.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_cors_headers_on_catalogue(self, handler):
        resp = await handler.handle_catalogue(_make_request({"page": "1"}))
        assert resp.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_cors_headers_on_search(self, handler):
        resp = await handler.handle_search(_make_request({"query": "test", "field": "title"}))
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
