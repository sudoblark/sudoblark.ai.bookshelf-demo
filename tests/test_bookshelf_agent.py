"""Tests for bookshelf-agent Lambda layer."""

from unittest.mock import MagicMock

import pydantic_ai.models as pydantic_ai_models
import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

pydantic_ai_models.ALLOW_MODEL_REQUESTS = False

# bookshelf-agent is on sys.path via conftest.py (mirrors Lambda /opt/python)
from agent import BookshelfAgent  # noqa: E402
from models import BookMetadata  # noqa: E402
from s3_toolset import build_s3_chunked_reader  # noqa: E402


class TestBookMetadata:
    """Tests for BookMetadata pydantic validators."""

    def test_isbn_hyphens_stripped(self):
        """Should remove hyphens from ISBN on validation."""
        m = BookMetadata(isbn="978-0-7432-7356-5")
        assert m.isbn == "9780743273565"

    def test_isbn_spaces_stripped(self):
        """Should remove spaces from ISBN on validation."""
        m = BookMetadata(isbn="978 0 7432 7356 5")
        assert m.isbn == "9780743273565"

    def test_year_too_old_becomes_none(self):
        """Should return None for years before 1000."""
        m = BookMetadata(published_year=500)
        assert m.published_year is None

    def test_year_too_future_becomes_none(self):
        """Should return None for years after 2100."""
        m = BookMetadata(published_year=2200)
        assert m.published_year is None

    def test_valid_year_preserved(self):
        """Should keep a valid year unchanged."""
        m = BookMetadata(published_year=2024)
        assert m.published_year == 2024

    def test_defaults_are_empty_strings(self):
        """Should default all string fields to empty string and optionals to None."""
        m = BookMetadata()
        assert m.title == ""
        assert m.author == ""
        assert m.isbn == ""
        assert m.publisher == ""
        assert m.description == ""
        assert m.confidence is None
        assert m.published_year is None

    def test_isbn_empty_string_preserved(self):
        """Should return empty string unchanged when isbn is explicitly empty."""
        m = BookMetadata(isbn="")
        assert m.isbn == ""


class TestBookshelfAgent:
    """Tests for BookshelfAgent."""

    def _make_agent(self) -> BookshelfAgent:
        return BookshelfAgent("test-model", MagicMock())

    def test_run_returns_book_metadata(self):
        """Should return a populated BookMetadata instance."""
        agent = self._make_agent()
        with agent._agent.override(
            model=TestModel(
                custom_output_args={
                    "title": "Dune",
                    "author": "Frank Herbert",
                    "isbn": "9780441013593",
                    "publisher": "Ace",
                    "published_year": 1965,
                    "description": "A science fiction epic.",
                    "confidence": 0.92,
                }
            )
        ):
            result = agent.run("Extract the book metadata.")

        assert isinstance(result, BookMetadata)
        assert result.title == "Dune"
        assert result.author == "Frank Herbert"
        assert result.isbn == "9780441013593"

    def test_run_model_failure_propagates(self):
        """Should propagate exceptions raised by the underlying model."""
        agent = self._make_agent()

        def failing_model(messages: list[ModelMessage], info: AgentInfo) -> None:
            raise UnexpectedModelBehavior("Model unavailable")

        with agent._agent.override(model=FunctionModel(failing_model)):
            with pytest.raises(Exception):
                agent.run("Extract the book metadata.")

    def test_run_with_empty_toolsets(self):
        """Should accept an empty toolsets list without error."""
        agent = self._make_agent()
        with agent._agent.override(model=TestModel(custom_output_args={"title": "Test Book"})):
            result = agent.run("Extract the book metadata.", toolsets=[])

        assert isinstance(result, BookMetadata)


class TestS3Toolset:
    """Tests for build_s3_chunked_reader toolset."""

    def _setup_s3(
        self, s3_client, content: bytes, bucket: str = "test-bucket", key: str = "book.jpg"
    ):
        s3_client.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        s3_client.put_object(Bucket=bucket, Key=key, Body=content)

    def _get_tool_fn(self, toolset, name: str):
        """Extract the raw callable from a FunctionToolset by tool name."""
        return toolset.tools[name].function

    def test_get_file_info_returns_metadata(self, s3_client):
        """Should return bucket, key, size_bytes, content_type, and chunk_size_bytes."""
        content = b"fake book image data"
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(s3_client, "test-bucket", "book.jpg")

        result = self._get_tool_fn(toolset, "get_file_info")()

        assert result["bucket"] == "test-bucket"
        assert result["key"] == "book.jpg"
        assert result["size_bytes"] == len(content)
        assert "content_type" in result
        assert result["chunk_size_bytes"] == 65_536

    def test_read_next_chunk_lazy_total_size(self, s3_client):
        """Should lazily fetch total_size via HEAD when called before get_file_info."""
        content = b"Hello World"
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(s3_client, "test-bucket", "book.jpg")

        result = self._get_tool_fn(toolset, "read_next_chunk")()

        assert result["total_size"] == len(content)
        assert result["bytes_read"] == len(content)

    def test_read_next_chunk_normal(self, s3_client):
        """Should return a chunk of data and advance position."""
        content = b"ABCDEFGHIJ"
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(s3_client, "test-bucket", "book.jpg", chunk_size_bytes=4)
        get_file_info = self._get_tool_fn(toolset, "get_file_info")
        read_next_chunk = self._get_tool_fn(toolset, "read_next_chunk")

        get_file_info()
        result = read_next_chunk()

        assert result["chunk"] == "ABCD"
        assert result["bytes_read"] == 4
        assert result["position"] == 4
        assert result["end_of_file"] is False

    def test_read_next_chunk_at_eof(self, s3_client):
        """Should return end_of_file=True when position reaches total size."""
        content = b"Hi"
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(
            s3_client, "test-bucket", "book.jpg", chunk_size_bytes=100
        )
        read_next_chunk = self._get_tool_fn(toolset, "read_next_chunk")

        read_next_chunk()  # reads all 2 bytes, position == total
        result = read_next_chunk()  # position >= total

        assert result["end_of_file"] is True
        assert result["bytes_read"] == 0

    def test_read_next_chunk_max_chunks_limit(self, s3_client):
        """Should return end_of_file=True once max_chunks is reached."""
        content = b"A" * 100
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(
            s3_client, "test-bucket", "book.jpg", chunk_size_bytes=20, max_chunks=1
        )
        get_file_info = self._get_tool_fn(toolset, "get_file_info")
        read_next_chunk = self._get_tool_fn(toolset, "read_next_chunk")

        get_file_info()
        read_next_chunk()  # chunks_read becomes 1
        result = read_next_chunk()  # max_chunks limit hit

        assert result["end_of_file"] is True
        assert result["bytes_read"] == 0

    def test_reset_position_rewinds(self, s3_client):
        """Should reset position to 0 so subsequent reads restart from the beginning."""
        content = b"ABCDEFGHIJ"
        self._setup_s3(s3_client, content)
        toolset = build_s3_chunked_reader(s3_client, "test-bucket", "book.jpg", chunk_size_bytes=4)
        read_next_chunk = self._get_tool_fn(toolset, "read_next_chunk")
        reset_position = self._get_tool_fn(toolset, "reset_position")

        read_next_chunk()  # reads "ABCD", position=4
        result = reset_position()
        assert result["position"] == 0

        result = read_next_chunk()
        assert result["chunk"] == "ABCD"
