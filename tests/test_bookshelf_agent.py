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
