"""
Copilot client integration shim.

This module provides a single function `extract_book_metadata(image_path)` which
wraps a real Copilot Studio agent call. For the demo it returns `None`, and
`extractor.py` will fall back to the placeholder extractor. When you integrate
with Copilot, implement the actual API call here and return a metadata dict
matching the expected schema.

Expected return shape (example):
{
  "id": "uuid",
  "filename": "cover.jpg",
  "title": "...",
  "author": "...",
  "isbn": "...",
  "publisher": "...",
  "published_year": 2021,
  "description": "...",
  "processed_at": "2026-01-27T12:00:00Z",
}

If `None` is returned, `extractor.extract_metadata` will use the local
placeholder extractor.
"""

from typing import Optional, Dict


def extract_book_metadata(image_path: str) -> Optional[Dict[str, any]]:
    """
    Call out to Copilot Studio to extract book metadata from `image_path`.

    Returns a metadata dict on success, or `None` if the call is not available
    or fails. Keep this function fast and robust; do not raise on transient
    failures — surface errors in logs instead.
    """
    # TODO: Implement real Copilot integration here.
    # Example stub for future implementation:
    # response = copilot_api.analyze_image(image_path, model='book-extractor')
    # if response.ok: return response.json()

    return None

# Copilot: Stub for communicating with a Copilot Studio agent.
# Later this will handle API calls for image-based metadata extraction.
# For now, leave as a skeleton with a TODO for integration.
# Keep all Copilot-specific logic in this file.
