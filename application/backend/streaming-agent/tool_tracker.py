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
