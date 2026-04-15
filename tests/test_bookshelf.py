"""Tests for bookshelf handler (overview, catalogue, search)."""

import importlib
import json
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from fastapi import Request
from moto import mock_aws

RAW_BUCKET = "test-raw-bucket"

# Sample books for seeding
SAMPLE_BOOKS = [
    {
        "upload_id": "book-001",
        "filename": "way_of_kings.jpg",
        "title": "The Way of Kings",
        "author": "Brandon Sanderson",
        "isbn": "9780765326355",
        "publisher": "Tor Books",
        "published_year": 2010,
        "description": "Epic fantasy novel",
        "confidence": 0.95,
    },
    {
        "upload_id": "book-002",
        "filename": "words_of_radiance.jpg",
        "title": "Words of Radiance",
        "author": "Brandon Sanderson",
        "isbn": "9780765326362",
        "publisher": "Tor Books",
        "published_year": 2014,
        "description": "Second book in Stormlight",
        "confidence": 0.92,
    },
    {
        "upload_id": "book-003",
        "filename": "name_of_the_wind.jpg",
        "title": "The Name of the Wind",
        "author": "Patrick Rothfuss",
        "isbn": "9780756404079",
        "publisher": "DAW Books",
        "published_year": 2007,
        "description": "First book of Kingkiller Chronicle",
        "confidence": 0.88,
    },
]


@pytest.fixture
def s3_client_with_books(aws_credentials):
    """Create S3 client and seed with sample books."""
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-2")
        client.create_bucket(
            Bucket=RAW_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )

        # Seed books
        for book in SAMPLE_BOOKS:
            author = book["author"].replace(" ", "_")
            year = book["published_year"]
            key = f"author={author}/published_year={year}/{book['upload_id']}.json"
            client.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode("utf-8"))

        yield client


@pytest.fixture
def bookshelf_handler(s3_client_with_books, monkeypatch):
    """Create BookshelfHandler with mocked S3."""
    monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
    sys.path.insert(
        0,
        __import__("os").path.join(
            __import__("os").path.dirname(__file__),
            "../application/backend/streaming-agent",
        ),
    )
    mod = importlib.import_module("bookshelf_handler")
    return mod.BookshelfHandler(s3_client=s3_client_with_books)


def _mock_request(query_params=None) -> Request:
    """Create a mock FastAPI Request for testing."""
    request = MagicMock(spec=Request)
    request.query_params = query_params or {}
    return request


# ---------------------------------------------------------------------------
# TestOverview
# ---------------------------------------------------------------------------


class TestOverview:
    @pytest.mark.asyncio
    async def test_overview_returns_correct_stats(self, bookshelf_handler):
        """Test GET /bookshelf/overview returns correct stats."""
        request = _mock_request()
        response = await bookshelf_handler.handle_overview(request)

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body["total_books"] == 3
        assert body["most_common_author"] == "Brandon Sanderson"
        assert body["most_common_author_count"] == 2

    @pytest.mark.asyncio
    async def test_overview_empty_bucket(self, monkeypatch):
        """Test overview with no books returns zeros."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-west-2")
            s3.create_bucket(
                Bucket=RAW_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )

            monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
            sys.path.insert(
                0,
                __import__("os").path.join(
                    __import__("os").path.dirname(__file__),
                    "../application/backend/streaming-agent",
                ),
            )
            mod = importlib.import_module("bookshelf_handler")
            handler = mod.BookshelfHandler(s3_client=s3)

            request = _mock_request()
            response = await handler.handle_overview(request)

            body = json.loads(response.body)
            assert body["total_books"] == 0
            assert body["most_common_author"] is None
            assert body["most_common_author_count"] == 0

    @pytest.mark.asyncio
    async def test_overview_cors_header_present(self, bookshelf_handler):
        """Test CORS header is present in response."""
        request = _mock_request()
        response = await bookshelf_handler.handle_overview(request)
        assert response.headers["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# TestCatalogue
# ---------------------------------------------------------------------------


class TestCatalogue:
    @pytest.mark.asyncio
    async def test_catalogue_page_1_with_default_page_size(self, bookshelf_handler):
        """Test GET /bookshelf/catalogue returns paginated books."""
        request = _mock_request({"page": "1", "page_size": "2"})

        response = await bookshelf_handler.handle_catalogue(request)
        assert response.status_code == 200

        body = json.loads(response.body)
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert body["total_books"] == 3
        assert body["total_pages"] == 2
        assert len(body["books"]) == 2

    @pytest.mark.asyncio
    async def test_catalogue_page_2(self, bookshelf_handler):
        """Test page 2 of catalogue."""
        request = _mock_request({"page": "2", "page_size": "2"})

        response = await bookshelf_handler.handle_catalogue(request)
        body = json.loads(response.body)

        assert body["page"] == 2
        assert len(body["books"]) == 1  # Only 1 book on page 2

    @pytest.mark.asyncio
    async def test_catalogue_page_size_capped_at_20(self, bookshelf_handler):
        """Test page_size is capped at 20."""
        request = _mock_request({"page": "1", "page_size": "100"})

        response = await bookshelf_handler.handle_catalogue(request)
        body = json.loads(response.body)

        assert body["page_size"] == 20

    @pytest.mark.asyncio
    async def test_catalogue_default_values(self, bookshelf_handler):
        """Test catalogue with no query params uses defaults."""
        request = _mock_request({})

        response = await bookshelf_handler.handle_catalogue(request)
        body = json.loads(response.body)

        assert body["page"] == 1
        assert body["page_size"] == 5  # Default

    @pytest.mark.asyncio
    async def test_catalogue_each_book_has_required_fields(self, bookshelf_handler):
        """Test each book has required fields."""
        request = _mock_request({"page": "1", "page_size": "5"})

        response = await bookshelf_handler.handle_catalogue(request)
        body = json.loads(response.body)
        book = body["books"][0]

        assert "book_id" in book
        assert "title" in book
        assert "author" in book
        assert "isbn" in book
        assert "publisher" in book
        assert "published_year" in book
        assert "description" in book
        assert "confidence" in book
        assert "s3_key" in book


# ---------------------------------------------------------------------------
# TestSearch
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_by_author(self, bookshelf_handler):
        """Test search by author."""
        request = _mock_request({"query": "sanderson", "field": "author"})

        response = await bookshelf_handler.handle_search(request)
        assert response.status_code == 200

        body = json.loads(response.body)
        assert body["total_results"] == 2
        assert body["query"] == "sanderson"
        assert body["field"] == "author"
        assert all("Sanderson" in book["author"] for book in body["books"])

    @pytest.mark.asyncio
    async def test_search_by_title(self, bookshelf_handler):
        """Test search by title."""
        request = _mock_request({"query": "wind", "field": "title"})

        response = await bookshelf_handler.handle_search(request)
        body = json.loads(response.body)

        assert body["total_results"] == 1
        assert body["books"][0]["title"] == "The Name of the Wind"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, bookshelf_handler):
        """Test search is case-insensitive."""
        request = _mock_request({"query": "BRANDON", "field": "author"})

        response = await bookshelf_handler.handle_search(request)
        body = json.loads(response.body)

        assert body["total_results"] == 2

    @pytest.mark.asyncio
    async def test_search_no_query_returns_error(self, bookshelf_handler):
        """Test search without query param returns error."""
        request = _mock_request({"field": "title"})

        response = await bookshelf_handler.handle_search(request)
        assert response.status_code == 500
        body = json.loads(response.body)
        assert "error" in body

    @pytest.mark.asyncio
    async def test_search_invalid_field_returns_error(self, bookshelf_handler):
        """Test search with invalid field returns error."""
        request = _mock_request({"query": "test", "field": "invalid"})

        response = await bookshelf_handler.handle_search(request)
        assert response.status_code == 500
        body = json.loads(response.body)
        assert "error" in body

    @pytest.mark.asyncio
    async def test_search_no_results(self, bookshelf_handler):
        """Test search with no matches returns empty list."""
        request = _mock_request({"query": "nonexistent", "field": "author"})

        response = await bookshelf_handler.handle_search(request)
        body = json.loads(response.body)

        assert body["total_results"] == 0
        assert body["books"] == []


# ---------------------------------------------------------------------------
# TestCorsHeaders
# ---------------------------------------------------------------------------


class TestCorsHeaders:
    @pytest.mark.asyncio
    async def test_cors_headers_on_catalogue(self, bookshelf_handler):
        """Test CORS headers are present on catalogue response."""
        request = _mock_request({"page": "1"})
        response = await bookshelf_handler.handle_catalogue(request)
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_cors_headers_on_search(self, bookshelf_handler):
        """Test CORS headers are present on search response."""
        request = _mock_request({"query": "test", "field": "title"})
        response = await bookshelf_handler.handle_search(request)
        assert response.headers["Access-Control-Allow-Origin"] == "*"
