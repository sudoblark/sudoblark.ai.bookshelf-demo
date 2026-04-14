"""Tests for streaming_models.py - Pydantic model validation."""

import importlib
import os
import sys

import pytest
from pydantic import ValidationError

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)
streaming_models = importlib.import_module("streaming_models")
StreamingBookMetadataResponse = streaming_models.StreamingBookMetadataResponse


class TestStreamingBookMetadataResponseDefaults:
    """Test field defaults and model instantiation."""

    def test_empty_model_uses_all_defaults(self):
        """Test that all fields have sensible defaults."""
        model = StreamingBookMetadataResponse()
        assert model.title == ""
        assert model.author == ""
        assert model.isbn == ""
        assert model.publisher == ""
        assert model.published_year is None
        assert model.description == ""
        assert model.confidence is None
        assert model.assistantMessage == ""
        assert model.readyToSave is False

    def test_string_fields_default_to_empty_string(self):
        """Test that string fields default to empty strings."""
        model = StreamingBookMetadataResponse()
        assert isinstance(model.title, str)
        assert isinstance(model.author, str)
        assert isinstance(model.isbn, str)
        assert isinstance(model.publisher, str)
        assert isinstance(model.description, str)
        assert isinstance(model.assistantMessage, str)

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        model = StreamingBookMetadataResponse()
        assert model.published_year is None
        assert model.confidence is None

    def test_ready_to_save_defaults_to_false(self):
        """Test that readyToSave defaults to False."""
        model = StreamingBookMetadataResponse()
        assert model.readyToSave is False


class TestStreamingBookMetadataResponsePublishedYearValidator:
    """Test published_year field validator."""

    # Valid years
    def test_valid_year_passes_through(self):
        """Test that valid years are preserved."""
        model = StreamingBookMetadataResponse(published_year=2020)
        assert model.published_year == 2020

    def test_year_1000_passes(self):
        """Test that year 1000 (lower bound) passes."""
        model = StreamingBookMetadataResponse(published_year=1000)
        assert model.published_year == 1000

    def test_year_2100_passes(self):
        """Test that year 2100 (upper bound) passes."""
        model = StreamingBookMetadataResponse(published_year=2100)
        assert model.published_year == 2100

    def test_current_year_passes(self):
        """Test that current year (2026) passes."""
        model = StreamingBookMetadataResponse(published_year=2026)
        assert model.published_year == 2026

    # Invalid years - out of range
    def test_year_below_1000_returns_none(self):
        """Test that years below 1000 are converted to None."""
        model = StreamingBookMetadataResponse(published_year=999)
        assert model.published_year is None

    def test_year_above_2100_returns_none(self):
        """Test that years above 2100 are converted to None."""
        model = StreamingBookMetadataResponse(published_year=2101)
        assert model.published_year is None

    def test_year_zero_returns_none(self):
        """Test that year 0 is converted to None."""
        model = StreamingBookMetadataResponse(published_year=0)
        assert model.published_year is None

    def test_negative_year_returns_none(self):
        """Test that negative years are converted to None."""
        model = StreamingBookMetadataResponse(published_year=-2020)
        assert model.published_year is None

    # None and empty values
    def test_none_returns_none(self):
        """Test that None is preserved."""
        model = StreamingBookMetadataResponse(published_year=None)
        assert model.published_year is None

    def test_empty_string_returns_none(self):
        """Test that empty string is converted to None."""
        model = StreamingBookMetadataResponse(published_year="")
        assert model.published_year is None

    # String placeholders that should return None
    def test_unknown_string_returns_none(self):
        """Test that 'Unknown' string is converted to None."""
        model = StreamingBookMetadataResponse(published_year="Unknown")
        assert model.published_year is None

    def test_unknown_lowercase_string_returns_none(self):
        """Test that 'unknown' (lowercase) is converted to None."""
        model = StreamingBookMetadataResponse(published_year="unknown")
        assert model.published_year is None

    def test_na_string_returns_none(self):
        """Test that 'N/A' is converted to None."""
        model = StreamingBookMetadataResponse(published_year="N/A")
        assert model.published_year is None

    def test_na_lowercase_string_returns_none(self):
        """Test that 'na' (lowercase) is converted to None."""
        model = StreamingBookMetadataResponse(published_year="na")
        assert model.published_year is None

    def test_not_found_string_returns_none(self):
        """Test that 'not found' is converted to None."""
        model = StreamingBookMetadataResponse(published_year="not found")
        assert model.published_year is None

    def test_not_visible_string_returns_none(self):
        """Test that 'not visible' is converted to None."""
        model = StreamingBookMetadataResponse(published_year="not visible")
        assert model.published_year is None

    # String years
    def test_valid_year_string_parses_to_int(self):
        """Test that valid year strings are parsed to int."""
        model = StreamingBookMetadataResponse(published_year="2020")
        assert model.published_year == 2020

    def test_valid_year_string_with_whitespace(self):
        """Test that valid year strings with whitespace are handled."""
        model = StreamingBookMetadataResponse(published_year="  2020  ")
        assert model.published_year == 2020

    def test_invalid_year_string_returns_none(self):
        """Test that invalid year strings are converted to None."""
        model = StreamingBookMetadataResponse(published_year="2101")  # Out of range
        assert model.published_year is None

    def test_non_numeric_string_returns_none(self):
        """Test that non-numeric strings are converted to None."""
        model = StreamingBookMetadataResponse(published_year="twenty twenty")
        assert model.published_year is None

    def test_partial_numeric_string_returns_none(self):
        """Test that partially numeric strings are converted to None."""
        model = StreamingBookMetadataResponse(published_year="2020-01-01")
        assert model.published_year is None


class TestStreamingBookMetadataResponseConfidenceValidation:
    """Test confidence field validation (0.0-1.0 range)."""

    def test_confidence_0_0_accepted(self):
        """Test that confidence 0.0 is accepted."""
        model = StreamingBookMetadataResponse(confidence=0.0)
        assert model.confidence == 0.0

    def test_confidence_1_0_accepted(self):
        """Test that confidence 1.0 is accepted."""
        model = StreamingBookMetadataResponse(confidence=1.0)
        assert model.confidence == 1.0

    def test_confidence_0_5_accepted(self):
        """Test that confidence 0.5 is accepted."""
        model = StreamingBookMetadataResponse(confidence=0.5)
        assert model.confidence == 0.5

    def test_confidence_negative_rejected(self):
        """Test that negative confidence is rejected."""
        with pytest.raises(ValidationError) as exc:
            StreamingBookMetadataResponse(confidence=-0.1)
        assert "greater than or equal to 0" in str(exc.value)

    def test_confidence_above_1_rejected(self):
        """Test that confidence above 1.0 is rejected."""
        with pytest.raises(ValidationError) as exc:
            StreamingBookMetadataResponse(confidence=1.1)
        assert "less than or equal to 1" in str(exc.value)

    def test_confidence_none_accepted(self):
        """Test that confidence None is accepted."""
        model = StreamingBookMetadataResponse(confidence=None)
        assert model.confidence is None


class TestStreamingBookMetadataResponseFieldAssignment:
    """Test field assignment and model construction."""

    def test_all_fields_can_be_set(self):
        """Test that all fields can be set during instantiation."""
        model = StreamingBookMetadataResponse(
            title="Test Book",
            author="Test Author",
            isbn="9780743273565",
            publisher="Test Publisher",
            published_year=2020,
            description="Test Description",
            confidence=0.95,
            assistantMessage="Test Message",
            readyToSave=True,
        )
        assert model.title == "Test Book"
        assert model.author == "Test Author"
        assert model.isbn == "9780743273565"
        assert model.publisher == "Test Publisher"
        assert model.published_year == 2020
        assert model.description == "Test Description"
        assert model.confidence == 0.95
        assert model.assistantMessage == "Test Message"
        assert model.readyToSave is True

    def test_partial_field_assignment(self):
        """Test that partial field assignment works with defaults."""
        model = StreamingBookMetadataResponse(
            title="Test Book",
            confidence=0.8,
        )
        assert model.title == "Test Book"
        assert model.author == ""  # Default
        assert model.confidence == 0.8
        assert model.readyToSave is False  # Default

    def test_model_serialization(self):
        """Test that model can be serialized to dict."""
        model = StreamingBookMetadataResponse(
            title="Test Book",
            published_year=2020,
        )
        data = model.model_dump()
        assert data["title"] == "Test Book"
        assert data["published_year"] == 2020
        assert data["readyToSave"] is False

    def test_model_to_json(self):
        """Test that model can be serialized to JSON."""
        model = StreamingBookMetadataResponse(
            title="Test Book",
            confidence=0.9,
        )
        json_str = model.model_dump_json()
        assert '"title":"Test Book"' in json_str
        assert '"confidence":0.9' in json_str
