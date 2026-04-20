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
def s3_with_books(aws_credentials, monkeypatch):
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
            client.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode())
        yield client


@pytest.fixture
def handler(s3_with_books):
    mod = importlib.import_module("bookshelf_handler")
    return mod.BookshelfHandler(s3_client=s3_with_books)


@pytest.fixture
def empty_handler(aws_credentials, monkeypatch):
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-2")
        client.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        mod = importlib.import_module("bookshelf_handler")
        yield mod.BookshelfHandler(s3_client=client)


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

    def test_empty_bucket_returns_empty_list(self, empty_handler):
        books = empty_handler._list_all_books()
        assert books == []

    def test_non_json_files_are_skipped(self, aws_credentials, monkeypatch):
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        with mock_aws():
            client = boto3.client("s3", region_name="eu-west-2")
            client.create_bucket(
                Bucket=RAW_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            client.put_object(Bucket=RAW_BUCKET, Key="cover.jpg", Body=b"image data")
            client.put_object(
                Bucket=RAW_BUCKET, Key="book.json", Body=json.dumps({"title": "Test"}).encode()
            )
            mod = importlib.import_module("bookshelf_handler")
            handler = mod.BookshelfHandler(s3_client=client)
            books = handler._list_all_books()
            assert len(books) == 1


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
        assert data["most_common_author"] == "Brandon Sanderson"
        assert data["most_common_author_count"] == 2

    @pytest.mark.asyncio
    async def test_empty_bucket_returns_zero_stats(self, empty_handler):
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
        resp = await handler.handle_search(_make_request({"query": "Sanderson", "field": "author"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 2

    @pytest.mark.asyncio
    async def test_search_by_title(self, handler):
        resp = await handler.handle_search(_make_request({"query": "wind", "field": "title"}))
        data = json.loads(resp.body)
        assert data["total_results"] == 1

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, handler):
        resp = await handler.handle_search(_make_request({"query": "sanderson", "field": "author"}))
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
