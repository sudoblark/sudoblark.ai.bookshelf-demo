"""ISBN lookup and validation toolset for pydantic-ai agents.

Provides tools to:
- Validate ISBN format (ISBN-10 vs ISBN-13)
- Query Google Books API for authoritative metadata
- Fallback to Open Library API if Google returns no results
- Handle rate limiting and errors gracefully

This toolset is injected into the BookshelfStreamingAgent to allow
the agent to validate extracted ISBNs against authoritative sources.
"""

import logging
import re
from typing import Optional

import httpx
from pydantic_ai import FunctionToolset

logger = logging.getLogger(__name__)

# Compile regex patterns for ISBN validation
ISBN_10_PATTERN = re.compile(r"^(?:\d{9}[\dXx])$")
ISBN_13_PATTERN = re.compile(r"^(?:97[89]\d{10})$")


def _normalize_isbn(isbn: str) -> str:
    """Remove hyphens, spaces, and normalize to digits only."""
    return isbn.replace("-", "").replace(" ", "").strip()


def _is_valid_isbn(isbn: str) -> tuple[bool, Optional[str]]:
    """Validate ISBN format and return (is_valid, isbn_type)."""
    normalized = _normalize_isbn(isbn)

    if ISBN_13_PATTERN.match(normalized):
        return True, "ISBN-13"
    elif ISBN_10_PATTERN.match(normalized):
        return True, "ISBN-10"
    else:
        return False, None


def _query_google_books(isbn: str, timeout: float = 5.0) -> Optional[dict]:
    """Query Google Books API for ISBN metadata.

    Returns None if no results or on error.
    """
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        if data.get("totalItems", 0) == 0:
            return None

        # Extract first result
        item = data["items"][0]
        volume_info = item.get("volumeInfo", {})

        # Normalize to our schema
        return {
            "title": volume_info.get("title", ""),
            "authors": ", ".join(volume_info.get("authors", [])),
            "publisher": volume_info.get("publisher", ""),
            "published_date": volume_info.get("publishedDate", ""),
            "description": volume_info.get("description", ""),
            "isbn": isbn,
            "source": "Google Books API",
        }
    except httpx.TimeoutException:
        logger.warning(f"Google Books API timeout for ISBN {isbn}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"Google Books API HTTP error for ISBN {isbn}: {e.response.status_code}")
        return None
    except Exception:
        logger.exception(f"Google Books API error for ISBN {isbn}")
        return None


def _query_openlibrary(isbn: str, timeout: float = 5.0) -> Optional[dict]:
    """Query Open Library API for ISBN metadata.

    Returns None if no results or on error.
    """
    try:
        url = f"https://openlibrary.org/isbn/{isbn}.json"
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()

        data = response.json()

        # Open Library structure is different - extract what we can
        # Note: May need to fetch author details separately
        return {
            "title": data.get("title", ""),
            "authors": ", ".join([a.get("name", "") for a in data.get("authors", [])]),
            "publisher": ", ".join(data.get("publishers", [])),
            "published_date": data.get("publish_date", ""),
            "description": data.get("description", {}).get("value", "")
            if isinstance(data.get("description"), dict)
            else data.get("description", ""),
            "isbn": isbn,
            "source": "Open Library API",
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info(f"ISBN {isbn} not found in Open Library")
        else:
            logger.warning(f"Open Library API HTTP error for ISBN {isbn}: {e.response.status_code}")
        return None
    except Exception:
        logger.exception(f"Open Library API error for ISBN {isbn}")
        return None


def build_isbn_toolset(enable_lookup: bool = True) -> FunctionToolset:
    """Return a FunctionToolset for ISBN validation and lookup.

    Args:
        enable_lookup: If False, only validation is enabled (no external API calls).
                       Useful for testing or when API quotas are exhausted.

    Returns:
        A FunctionToolset exposing validate_isbn and lookup_isbn_metadata.
    """
    toolset = FunctionToolset()

    @toolset.tool_plain
    def validate_isbn(isbn: str) -> dict:
        """Validate ISBN format and structure.

        Args:
            isbn: The ISBN string to validate (can include hyphens/spaces).

        Returns:
            dict with keys: is_valid, isbn_type, normalized_isbn, error.
        """
        if not isbn or not isbn.strip():
            return {
                "is_valid": False,
                "error": "ISBN is empty or whitespace",
            }

        normalized = _normalize_isbn(isbn)
        is_valid, isbn_type = _is_valid_isbn(normalized)

        if is_valid:
            return {
                "is_valid": True,
                "isbn_type": isbn_type,
                "normalized_isbn": normalized,
            }
        else:
            return {
                "is_valid": False,
                "error": f"Invalid ISBN format: {isbn} (expected 10 or 13 digits)",
            }

    if enable_lookup:

        @toolset.tool_plain
        def lookup_isbn_metadata(isbn: str) -> dict:
            """Look up book metadata from authoritative ISBN databases.

            Queries Google Books API first, then falls back to Open Library
            if no results are found. Returns structured metadata or error.

            Args:
                isbn: The ISBN to look up (will be normalized automatically).

            Returns:
                dict with keys: success, title, authors, publisher, published_date,
                description, isbn, source (API name), or error.
            """
            # Validate ISBN first
            validation = validate_isbn(isbn)
            if not validation.get("is_valid"):
                return {
                    "success": False,
                    "error": validation.get("error", "Invalid ISBN"),
                }

            normalized = validation["normalized_isbn"]

            # Try Google Books first
            logger.info(f"Querying Google Books API for ISBN {normalized}")
            result = _query_google_books(normalized)
            if result:
                return {"success": True, **result}

            # Fallback to Open Library
            logger.info(
                f"Google Books returned no results, trying Open Library for ISBN {normalized}"
            )
            result = _query_openlibrary(normalized)
            if result:
                return {"success": True, **result}

            # No results from either API
            return {
                "success": False,
                "error": f"ISBN {normalized} not found in Google Books or Open Library",
            }

    return toolset
