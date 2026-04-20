"""Tests for ToolTracker."""

import importlib
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)

tracker_mod = importlib.import_module("tool_tracker")
ToolTracker = tracker_mod.ToolTracker


class TestToolTrackerRecord:
    """Test ToolTracker.record()."""

    def test_record_appends_execution(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [{"title": "Book"}], 12.5)
        assert len(tracker.executions) == 1

    def test_record_stores_tool_name(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 5.0)
        assert tracker.executions[0].name == "list_books"

    def test_record_stores_inputs(self):
        tracker = ToolTracker()
        tracker.record("search_books", 'query="Sanderson"', [], 7.0)
        assert tracker.executions[0].inputs == 'query="Sanderson"'

    def test_record_stores_execution_time(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 42.3)
        assert tracker.executions[0].execution_time_ms == 42.3

    def test_record_multiple_appends_in_order(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 5.0)
        tracker.record("search_books", "query=test", [], 3.0)
        assert tracker.executions[0].name == "list_books"
        assert tracker.executions[1].name == "search_books"


class TestToolTrackerGetExecutions:
    """Test ToolTracker.get_executions()."""

    def test_returns_empty_list_initially(self):
        tracker = ToolTracker()
        assert tracker.get_executions() == []

    def test_returns_all_recorded_executions(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 5.0)
        tracker.record("get_overview", "(no parameters)", {"total_books": 3}, 2.0)
        assert len(tracker.get_executions()) == 2


class TestToolTrackerClear:
    """Test ToolTracker.clear()."""

    def test_clear_empties_executions(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 5.0)
        tracker.clear()
        assert tracker.get_executions() == []

    def test_clear_allows_new_records(self):
        tracker = ToolTracker()
        tracker.record("list_books", "(no parameters)", [], 5.0)
        tracker.clear()
        tracker.record("search_books", "query=test", [], 3.0)
        assert len(tracker.get_executions()) == 1


class TestToolTrackerSummarizeResult:
    """Test ToolTracker._summarize_result()."""

    def test_none_result_returns_no_results(self):
        assert ToolTracker._summarize_result("list_books", None) == "No results"

    def test_empty_dict_returns_no_results(self):
        assert ToolTracker._summarize_result("list_books", {}) == "No results"

    def test_error_in_result_returns_failed_message(self):
        result = {"error": "timeout"}
        summary = ToolTracker._summarize_result("list_books", result)
        assert "failed" in summary.lower()
        assert "timeout" in summary

    def test_extract_ocr_text_with_lines(self):
        result = {"line_count": 5, "confidence": 0.95}
        summary = ToolTracker._summarize_result("extract_ocr_text", result)
        assert "5 lines" in summary
        assert "95.0%" in summary

    def test_extract_isbn_found(self):
        result = {"isbn": "9780765326355", "pattern_matched": "ISBN-13"}
        summary = ToolTracker._summarize_result("extract_isbn", result)
        assert "9780765326355" in summary

    def test_extract_isbn_not_found(self):
        result = {"isbn": None}
        summary = ToolTracker._summarize_result("extract_isbn", result)
        assert "No ISBN" in summary

    def test_lookup_isbn_metadata_found(self):
        result = {"title": "The Way of Kings", "source": "Google Books API"}
        summary = ToolTracker._summarize_result("lookup_isbn_metadata", result)
        assert "The Way of Kings" in summary

    def test_lookup_by_title_author_found(self):
        result = {"title": "Dune", "isbn": "9780441013593"}
        summary = ToolTracker._summarize_result("lookup_by_title_author", result)
        assert "Dune" in summary
        assert "9780441013593" in summary

    def test_update_metadata_field(self):
        result = {"field": "title", "value": "New Title", "status": "updated"}
        summary = ToolTracker._summarize_result("update_metadata_field", result)
        assert "title" in summary
        assert "New Title" in summary

    def test_list_books_with_results(self):
        result = [{"title": "Book 1"}, {"title": "Book 2"}]
        summary = ToolTracker._summarize_result("list_books", result)
        assert "2 books" in summary

    def test_list_books_single_book(self):
        result = [{"title": "Book 1"}]
        summary = ToolTracker._summarize_result("list_books", result)
        assert "1 book" in summary

    def test_search_books_with_results(self):
        result = [{"title": "Book 1"}, {"title": "Book 2"}, {"title": "Book 3"}]
        summary = ToolTracker._summarize_result("search_books", result)
        assert "3 matching" in summary

    def test_get_overview(self):
        result = {
            "total_books": 10,
            "most_common_author": "Sanderson",
            "most_common_author_count": 4,
        }
        summary = ToolTracker._summarize_result("get_overview", result)
        assert "10 total" in summary
        assert "Sanderson" in summary

    def test_unknown_tool_list_result(self):
        result = [1, 2, 3]
        summary = ToolTracker._summarize_result("unknown_tool", result)
        assert "3" in summary

    def test_unknown_tool_dict_result(self):
        result = {"a": 1, "b": 2}
        summary = ToolTracker._summarize_result("unknown_tool", result)
        assert "2" in summary

    def test_unknown_tool_scalar_result(self):
        summary = ToolTracker._summarize_result("unknown_tool", "some string")
        assert summary == "Result retrieved"
