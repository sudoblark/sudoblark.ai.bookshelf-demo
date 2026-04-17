"""Tool execution tracker for audit trail generation."""

from typing import Any, List

from streaming_models import ToolExecution


class ToolTracker:
    """Tracks tool executions for audit trail and transparency."""

    def __init__(self):
        self.executions: List[ToolExecution] = []

    def record(
        self,
        tool_name: str,
        inputs_str: str,
        result: Any,
        execution_time_ms: float,
    ) -> None:
        """Record a tool execution.

        Args:
            tool_name: Name of the tool called
            inputs_str: Human-readable string of inputs
            result: The result from the tool
            execution_time_ms: Time taken in milliseconds
        """
        result_summary = self._summarize_result(tool_name, result)

        execution = ToolExecution(
            name=tool_name,
            inputs=inputs_str,
            result_summary=result_summary,
            execution_time_ms=execution_time_ms,
        )
        self.executions.append(execution)

    @staticmethod
    def _summarize_result(tool_name: str, result: Any) -> str:
        """Generate a brief, human-readable summary of tool results."""
        if result is None or not result:
            return "No results"

        # Metadata extraction tools
        if tool_name == "extract_ocr_text":
            if isinstance(result, dict):
                if "error" in result:
                    return f"OCR failed: {result['error']}"
                line_count = result.get("line_count", 0)
                confidence = result.get("confidence", 0.0)
                return f"Extracted {line_count} lines (confidence: {confidence:.1%})"
            return "OCR extraction completed"

        if tool_name == "extract_isbn":
            if isinstance(result, dict):
                if "error" in result:
                    return f"ISBN extraction failed: {result['error']}"
                isbn = result.get("isbn")
                if isbn:
                    return f"Found ISBN: {isbn}"
                return "No ISBN found on cover"
            return "ISBN extraction completed"

        if tool_name == "lookup_isbn_metadata":
            if isinstance(result, dict):
                if "error" in result:
                    return f"ISBN lookup failed: {result['error']}"
                title = result.get("title", "Unknown")
                source = result.get("source", "Database")
                return f"Found '{title}' via {source}"
            return "ISBN lookup completed"

        if tool_name == "lookup_by_title_author":
            if isinstance(result, dict):
                if "error" in result:
                    return f"Title/author lookup failed: {result['error']}"
                title = result.get("title", "Unknown")
                isbn = result.get("isbn", "N/A")
                return f"Found '{title}' (ISBN: {isbn})"
            return "Title/author lookup completed"

        if tool_name == "update_metadata_field":
            if isinstance(result, dict):
                if "error" in result:
                    return f"Update failed: {result['error']}"
                field = result.get("field", "field")
                value = result.get("value", "")
                return f"Updated {field} to: {value}"
            return "Metadata field updated"

        # Bookshelf query tools
        if tool_name == "list_books":
            books = result if isinstance(result, list) else []
            count = len(books)
            return f"Retrieved {count} book{'' if count == 1 else 's'}"

        if tool_name == "search_books":
            books = result if isinstance(result, list) else []
            count = len(books)
            return f"Found {count} matching book{'' if count == 1 else 's'}"

        if tool_name == "get_overview":
            if isinstance(result, dict):
                total = result.get("total_books", 0)
                author = result.get("most_common_author", "Unknown")
                count = result.get("most_common_author_count", 0)
                return f"{total} total books; most common author: {author} ({count} books)"
            return "Overview retrieved"

        # Fallback for unknown tools
        if isinstance(result, list):
            return f"Retrieved {len(result)} item(s)"
        if isinstance(result, dict):
            return f"Retrieved data with {len(result)} field(s)"

        return "Result retrieved"

    def get_executions(self) -> List[ToolExecution]:
        """Get all recorded executions."""
        return self.executions

    def clear(self) -> None:
        """Clear execution history."""
        self.executions = []
