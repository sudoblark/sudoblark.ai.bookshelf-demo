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
        FunctionToolset with tools: list_books, search_books, get_overview,
        get_similar_books, get_similarity_graph.
    """
    toolset = FunctionToolset()

    @toolset.tool_plain
    def list_books() -> List[Dict]:  # pragma: no cover
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
    def search_books(query: str, field: str = "title") -> List[Dict]:  # pragma: no cover
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
    def get_overview() -> Dict:  # pragma: no cover
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

    @toolset.tool_plain
    def get_similar_books(book_id: str, limit: int = 5) -> List[Dict]:  # pragma: no cover
        """Find books most similar to the given book by semantic embedding similarity.

        Args:
            book_id: The upload_id of the book to find similar books for.
            limit: Maximum number of similar books to return (default 5).

        Returns a list of similar books with title, author, similarity score, and s3_key.
        """
        try:
            start = time.time()
            results: List[Dict] = bookshelf_handler._compute_related(book_id, limit)
            elapsed_ms = (time.time() - start) * 1000

            if tracker:
                tracker.record(
                    tool_name="get_similar_books",
                    inputs_str=f'book_id="{book_id}", limit={limit}',
                    result=results,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(
                f"Agent queried get_similar_books: book_id={book_id}, "
                f"{len(results)} results ({elapsed_ms:.1f}ms)"
            )
            return results
        except Exception as e:
            logger.exception("Agent tool error in get_similar_books: %s", e)
            return []

    @toolset.tool_plain
    def get_similarity_graph(threshold: float = 0.5) -> Dict:  # pragma: no cover
        """Get the full book similarity graph as nodes and weighted edges.

        Args:
            threshold: Minimum cosine similarity for an edge to be included (default 0.5).

        Returns a dict with 'nodes' (list of books) and 'edges' (pairs with similarity weight).
        """
        try:
            start = time.time()
            graph: Dict = bookshelf_handler._compute_graph(threshold)
            elapsed_ms = (time.time() - start) * 1000

            if tracker:
                tracker.record(
                    tool_name="get_similarity_graph",
                    inputs_str=f"threshold={threshold}",
                    result=graph,
                    execution_time_ms=elapsed_ms,
                )

            logger.info(
                f"Agent queried get_similarity_graph: threshold={threshold}, "
                f"{len(graph.get('nodes', []))} nodes, "
                f"{len(graph.get('edges', []))} edges ({elapsed_ms:.1f}ms)"
            )
            return graph
        except Exception as e:
            logger.exception("Agent tool error in get_similarity_graph: %s", e)
            return {"nodes": [], "edges": []}

    return toolset
