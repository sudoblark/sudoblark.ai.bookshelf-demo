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

        # Check for errors first
        if isinstance(result, dict) and "error" in result:
            return f"{tool_name} failed: {result['error']}"

        # Strategy dict maps tool names to summarization functions
        summarizers = {
            "extract_ocr_text": lambda r: (
                f"Extracted {r.get('line_count', 0)} lines "
                f"(confidence: {r.get('confidence', 0.0):.1%})"
                if isinstance(r, dict)
                else "OCR completed"
            ),
            "extract_isbn": lambda r: (
                f"Found ISBN: {r.get('isbn')}"
                if isinstance(r, dict) and r.get("isbn")
                else "No ISBN found"
            ),
            "lookup_isbn_metadata": lambda r: (
                f"Found '{r.get('title', 'Unknown')}' via {r.get('source', 'Database')}"
                if isinstance(r, dict)
                else "Lookup completed"
            ),
            "lookup_by_title_author": lambda r: (
                f"Found '{r.get('title', 'Unknown')}' (ISBN: {r.get('isbn', 'N/A')})"
                if isinstance(r, dict)
                else "Lookup completed"
            ),
            "update_metadata_field": lambda r: (
                f"Updated {r.get('field', 'field')} to: {r.get('value', '')}"
                if isinstance(r, dict)
                else "Update completed"
            ),
            "list_books": lambda r: (
                f"Retrieved {len(r)} book{'s' if len(r) != 1 else ''}"
                if isinstance(r, list)
                else "Retrieval completed"
            ),
            "search_books": lambda r: (
                f"Found {len(r)} matching book{'s' if len(r) != 1 else ''}"
                if isinstance(r, list)
                else "Search completed"
            ),
            "get_overview": lambda r: (
                f"{r.get('total_books', 0)} total; "
                f"top author: {r.get('most_common_author', 'Unknown')} "
                f"({r.get('most_common_author_count', 0)} books)"
                if isinstance(r, dict)
                else "Overview completed"
            ),
            "get_similar_books": lambda r: (
                f"Found {len(r)} similar book{'s' if len(r) != 1 else ''}"
                if isinstance(r, list)
                else "Similarity search completed"
            ),
            "get_similarity_graph": lambda r: (
                f"{len(r.get('nodes', []))} nodes, {len(r.get('edges', []))} edges"
                if isinstance(r, dict)
                else "Graph computed"
            ),
        }

        summarizer = summarizers.get(tool_name)
        if summarizer:
            return summarizer(result)

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
