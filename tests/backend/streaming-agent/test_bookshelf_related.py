"""Tests for BookshelfHandler.handle_related() and handle_similarity_graph()."""

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

RAW_BUCKET = "test-raw-related"
TRACKING_TABLE = "test-tracking-related"

# Three books: book-001 and book-002 share a near-identical vector; book-003 is orthogonal.
SAMPLE_BOOKS = [
    {
        "upload_id": "book-001",
        "title": "Guards! Guards!",
        "author": "Terry Pratchett",
        "published_year": 1989,
    },
    {
        "upload_id": "book-002",
        "title": "Men at Arms",
        "author": "Terry Pratchett",
        "published_year": 1993,
    },
    {
        "upload_id": "book-003",
        "title": "American Gods",
        "author": "Neil Gaiman",
        "published_year": 2001,
    },
]

_BASE = [1.0, 0.0, 0.0, 0.0]
_NEAR = [0.99, 0.14, 0.0, 0.0]
_FAR = [0.0, 0.0, 1.0, 0.0]

EMBEDDINGS = {
    "book-001": _BASE,
    "book-002": _NEAR,
    "book-003": _FAR,
}


def _book_key(book: dict) -> str:
    author = book["author"].replace(" ", "_")
    return f"author={author}/published_year={book['published_year']}/{book['upload_id']}.json"


def _make_request(params: dict = None):
    req = MagicMock()
    req.query_params = params or {}
    return req


@pytest.fixture
def aws_with_books_and_embeddings(aws_credentials, monkeypatch):
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
            emb_key = key.replace(".json", ".embedding.json")

            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode())
            s3.put_object(
                Bucket=RAW_BUCKET,
                Key=emb_key,
                Body=json.dumps(
                    {"upload_id": book["upload_id"], "embedding": EMBEDDINGS[book["upload_id"]]}
                ).encode(),
            )

            # Seed tracking record with analysed + embedding stages.
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
def handler(aws_with_books_and_embeddings):
    s3, dynamodb = aws_with_books_and_embeddings
    mod = importlib.import_module("bookshelf_handler")
    return mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)


class TestHandleRelated:
    """Test BookshelfHandler.handle_related()."""

    @pytest.mark.asyncio
    async def test_returns_200(self, handler):
        resp = await handler.handle_related(_make_request(), "book-001")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self, handler):
        resp = await handler.handle_related(_make_request(), "book-001")
        data = json.loads(resp.body)
        assert data["file_id"] == "book-001"
        assert isinstance(data["related"], list)

    @pytest.mark.asyncio
    async def test_excludes_target_book(self, handler):
        resp = await handler.handle_related(_make_request(), "book-001")
        data = json.loads(resp.body)
        ids = [b["file_id"] for b in data["related"]]
        assert "book-001" not in ids

    @pytest.mark.asyncio
    async def test_respects_limit_param(self, handler):
        resp = await handler.handle_related(_make_request({"limit": "1"}), "book-001")
        data = json.loads(resp.body)
        assert len(data["related"]) <= 1

    @pytest.mark.asyncio
    async def test_sorted_by_similarity_descending(self, handler):
        resp = await handler.handle_related(_make_request(), "book-001")
        data = json.loads(resp.body)
        sims = [b["similarity"] for b in data["related"]]
        assert sims == sorted(sims, reverse=True)

    @pytest.mark.asyncio
    async def test_book_002_ranked_above_book_003(self, handler):
        """book-002 is more similar to book-001 than book-003."""
        resp = await handler.handle_related(_make_request(), "book-001")
        data = json.loads(resp.body)
        ids = [b["file_id"] for b in data["related"]]
        assert ids.index("book-002") < ids.index("book-003")

    @pytest.mark.asyncio
    async def test_has_valid_similarity_scores(self, handler):
        resp = await handler.handle_related(_make_request(), "book-001")
        data = json.loads(resp.body)
        for book in data["related"]:
            assert "similarity" in book
            assert -1.0 <= book["similarity"] <= 1.0

    @pytest.mark.asyncio
    async def test_unknown_file_id_returns_empty_list(self, handler):
        resp = await handler.handle_related(_make_request(), "book-999")
        assert resp.status_code == 200
        data = json.loads(resp.body)
        assert data["related"] == []

    @pytest.mark.asyncio
    async def test_book_without_embedding_stage_returns_empty_list(
        self, aws_credentials, monkeypatch
    ):
        """A book tracked as analysed but with no embedding stage returns empty related."""
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-west-2")
            s3.create_bucket(
                Bucket=RAW_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            book = SAMPLE_BOOKS[0]
            key = _book_key(book)
            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode())

            dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
            table = dynamodb.create_table(
                TableName=TRACKING_TABLE,
                KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            # Analysed stage only — no embedding stage
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

            mod = importlib.import_module("bookshelf_handler")
            h = mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
            resp = await h.handle_related(_make_request(), "book-001")
            assert resp.status_code == 200
            data = json.loads(resp.body)
            assert data["related"] == []

    @pytest.mark.asyncio
    async def test_no_other_embeddings_returns_empty_list(self, aws_credentials, monkeypatch):
        """When only the target has an embedding stage, related is empty."""
        monkeypatch.setenv("RAW_BUCKET", RAW_BUCKET)
        monkeypatch.setenv("TRACKING_TABLE", TRACKING_TABLE)
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-west-2")
            s3.create_bucket(
                Bucket=RAW_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
            )
            book = SAMPLE_BOOKS[0]
            key = _book_key(book)
            emb_key = key.replace(".json", ".embedding.json")
            s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=json.dumps(book).encode())
            s3.put_object(
                Bucket=RAW_BUCKET,
                Key=emb_key,
                Body=json.dumps({"upload_id": "book-001", "embedding": _BASE}).encode(),
            )

            dynamodb = boto3.resource("dynamodb", region_name="eu-west-2")
            table = dynamodb.create_table(
                TableName=TRACKING_TABLE,
                KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "upload_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.put_item(
                Item={
                    "upload_id": "book-001",
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

            mod = importlib.import_module("bookshelf_handler")
            h = mod.BookshelfHandler(s3_client=s3, dynamodb_resource=dynamodb)
            resp = await h.handle_related(_make_request(), "book-001")
            data = json.loads(resp.body)
            assert data["related"] == []


class TestHandleSimilarityGraph:
    """Test BookshelfHandler.handle_similarity_graph()."""

    @pytest.mark.asyncio
    async def test_returns_200(self, handler):
        resp = await handler.handle_similarity_graph(_make_request())
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_nodes_and_edges(self, handler):
        resp = await handler.handle_similarity_graph(_make_request())
        data = json.loads(resp.body)
        assert "nodes" in data
        assert "edges" in data
        assert "threshold" in data

    @pytest.mark.asyncio
    async def test_node_count_matches_books_with_embeddings(self, handler):
        resp = await handler.handle_similarity_graph(_make_request())
        data = json.loads(resp.body)
        assert len(data["nodes"]) == 3

    @pytest.mark.asyncio
    async def test_low_threshold_includes_more_edges(self, handler):
        resp_low = await handler.handle_similarity_graph(_make_request({"threshold": "0.0"}))
        resp_high = await handler.handle_similarity_graph(_make_request({"threshold": "0.99"}))
        edges_low = json.loads(resp_low.body)["edges"]
        edges_high = json.loads(resp_high.body)["edges"]
        assert len(edges_low) >= len(edges_high)

    @pytest.mark.asyncio
    async def test_edge_has_source_target_weight(self, handler):
        resp = await handler.handle_similarity_graph(_make_request({"threshold": "0.0"}))
        data = json.loads(resp.body)
        for edge in data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "weight" in edge
