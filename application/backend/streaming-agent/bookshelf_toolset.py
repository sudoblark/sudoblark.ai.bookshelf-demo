"""Toolset for querying bookshelf data via pydantic-ai agent."""

import logging
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from pydantic_ai import FunctionToolset
from tool_tracker import ToolTracker

logger = logging.getLogger(__name__)


def build_bookshelf_toolset(
    bookshelf_handler: Any, tracker: Optional[ToolTracker] = None
) -> FunctionToolset:
    """Build a toolset that gives the agent access to bookshelf query functions.

    Args:
        bookshelf_handler: Instance of BookshelfHandler with S3 access.

    Returns:
        FunctionToolset with tools: list_books, search_books, get_overview.
    """
    toolset = FunctionToolset()

    @toolset.tool_plain
    def list_books() -> List[Dict]:
        """Get all books from the user's bookshelf.

        Returns a list of books with metadata: title, author, isbn, publisher,
        published_year, description, confidence, s3_key.
        """
        try:
            start = time.time()
            books: List[Dict] = bookshelf_handler._list_all_books()
            elapsed_ms = (time.time() - start) * 1000

            if tracker:
                tracker.record(
                    tool_name="list_books",
                    inputs_str="(no parameters)",
                    result=books,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(
                f"Agent queried list_books: {len(books)} books returned ({elapsed_ms:.1f}ms)"
            )
            return books
        except Exception as e:
            logger.exception("Agent tool error in list_books: %s", e)
            return []

    @toolset.tool_plain
    def search_books(query: str, field: str = "title") -> List[Dict]:
        """Search books by title or author.

        Args:
            query: Search term (case-insensitive substring match).
            field: Field to search in ("title" or "author").

        Returns a list of matching books.
        """
        try:
            start = time.time()

            if field not in ["title", "author"]:
                logger.warning(f"Agent used invalid field: {field}")
                field = "title"

            books = bookshelf_handler._list_all_books()
            filtered = [b for b in books if query.lower() in str(b.get(field, "")).lower()]

            elapsed_ms = (time.time() - start) * 1000

            if tracker:
                tracker.record(
                    tool_name="search_books",
                    inputs_str=f'query="{query}", field="{field}"',
                    result=filtered,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(
                f"Agent searched books: query={query}, field={field}, "
                f"results={len(filtered)} ({elapsed_ms:.1f}ms)"
            )
            return filtered
        except Exception as e:
            logger.exception("Agent tool error in search_books: %s", e)
            return []

    @toolset.tool_plain
    def get_overview() -> Dict:
        """Get bookshelf overview statistics.

        Returns:
            Dict with total_books, most_common_author, most_common_author_count.
        """
        try:
            start = time.time()

            books = bookshelf_handler._list_all_books()
            total_books = len(books)

            if total_books == 0:
                result = {
                    "total_books": 0,
                    "most_common_author": None,
                    "most_common_author_count": 0,
                }
                elapsed_ms = (time.time() - start) * 1000
                if tracker:
                    tracker.record(
                        tool_name="get_overview",
                        inputs_str="(no parameters)",
                        result=result,
                        execution_time_ms=elapsed_ms,
                    )
                return result

            authors = [b["author"] for b in books if b.get("author")]
            author_counts = Counter(authors)
            most_common = author_counts.most_common(1)
            most_common_author, count = most_common[0] if most_common else (None, 0)

            stats = {
                "total_books": total_books,
                "most_common_author": most_common_author,
                "most_common_author_count": count,
            }

            elapsed_ms = (time.time() - start) * 1000

            if tracker:
                tracker.record(
                    tool_name="get_overview",
                    inputs_str="(no parameters)",
                    result=stats,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(f"Agent queried overview: {stats} ({elapsed_ms:.1f}ms)")
            return stats
        except Exception as e:
            logger.exception("Agent tool error in get_overview: %s", e)
            return {
                "total_books": 0,
                "most_common_author": None,
                "most_common_author_count": 0,
            }

    return toolset
