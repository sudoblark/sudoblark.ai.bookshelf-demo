
"""
Metadata extraction module for book cover images.

This module is responsible for extracting metadata from image files
and returning structured data as dictionaries. Currently, it returns
placeholder metadata; future integration with a Copilot Studio agent
will enhance this with intelligent extraction.

Design:
- Single responsibility: transform image file path -> metadata dictionary
- Handles file I/O and error cases gracefully
- Returns consistent metadata structure
- Includes integration points for future Copilot API calls
"""

from pathlib import Path
from datetime import datetime
import uuid
import json
from typing import Dict, List, Optional

from logger import get_logger
from llm_client import extract_book_metadata

logger = get_logger(__name__)


# Placeholder metadata structure (can be expanded)
METADATA_SCHEMA = {
    "filename": str,
    "title": str,
    "author": str,
    "isbn": str,
    "publisher": str,
    "published_year": int,
    "description": str,
    "processed_at": str,  # ISO 8601 timestamp
}


class MetadataExtractionError(Exception):
    """Raised when metadata extraction fails."""
    pass


def extract_metadata(image_path: str) -> Dict[str, any]:
    """
    Extract metadata from a book cover image.
    
    Currently returns placeholder metadata. Future versions will integrate
    with a Copilot Studio agent for intelligent extraction.
    
    Args:
        image_path: Absolute path to the image file.
    
    Returns:
        Dictionary containing extracted metadata with keys matching METADATA_SCHEMA.
    
    Raises:
        MetadataExtractionError: If the file cannot be read or processed.
    
    Example:
        metadata = extract_metadata("/path/to/cover.jpg")
        print(metadata["title"])
    """
    logger.debug(f"Starting metadata extraction for: {image_path}")
    
    image_path = Path(image_path)
    
    # Validate file exists and is readable
    if not image_path.exists():
        error_msg = f"Image file does not exist: {image_path}"
        logger.error(error_msg)
        raise MetadataExtractionError(error_msg)
    
    if not image_path.is_file():
        error_msg = f"Path is not a file: {image_path}"
        logger.error(error_msg)
        raise MetadataExtractionError(error_msg)
    
    try:
        # Check file is readable
        if not image_path.stat().st_size > 0:
            error_msg = f"Image file is empty: {image_path}"
            logger.error(error_msg)
            raise MetadataExtractionError(error_msg)
    except (OSError, IOError) as e:
        error_msg = f"Cannot access image file {image_path}: {e}"
        logger.error(error_msg)
        raise MetadataExtractionError(error_msg)
    
    # Extract basic file information
    filename = image_path.name
    
    # Get current timestamp in ISO 8601 format
    processed_at = datetime.utcnow().isoformat() + "Z"
    
    # Attempt to use Copilot Studio agent first (if configured).
    try:
        copilot_result = extract_book_metadata(str(image_path))
    except Exception as e:
        logger.warning(f"Copilot extraction failed: {e}")
        copilot_result = None

    if copilot_result and isinstance(copilot_result, dict):
        # Ensure essential fields exist; fallback to placeholders where missing.
        if 'filename' not in copilot_result:
            copilot_result['filename'] = filename
        if 'processed_at' not in copilot_result:
            copilot_result['processed_at'] = processed_at
        metadata = copilot_result
    else:
        # Fallback to local placeholder extractor
        metadata = _extract_placeholder_metadata(filename, processed_at)
    
    logger.info(f"Metadata extracted for: {filename}")
    logger.debug(f"Extracted metadata: {json.dumps(metadata, indent=2)}")
    
    return metadata


def _extract_placeholder_metadata(filename: str, processed_at: str) -> Dict[str, any]:
    """
    Generate placeholder metadata.
    
    This is a temporary implementation that returns a basic metadata structure.
    In production, this will be replaced by intelligent extraction via a 
    Copilot Studio agent.
    
    Args:
        filename: Name of the image file.
        processed_at: ISO 8601 timestamp of processing.
    
    Returns:
        Dictionary with placeholder metadata.
    """
    metadata = {
        # Unique identifier for this record
        "id": str(uuid.uuid4()),
        "filename": filename,
        "title": "Extracted Title",
        "author": "Extracted Author",
        "isbn": "Extracted ISBN",
        "publisher": "Extracted Publisher",
        "published_year": None,
        "description": "Placeholder metadata - awaiting Copilot integration",
        "processed_at": processed_at,
    }
    
    return metadata


def extract_metadata_batch(image_paths: List[str]) -> List[Dict[str, any]]:
    """
    Extract metadata from multiple image files.
    
    Processes a list of image paths and returns a list of metadata dictionaries.
    Failures are logged but do not stop processing of other files.
    
    Args:
        image_paths: Iterable of absolute file paths to image files.
    
    Returns:
        List of metadata dictionaries. Failed extractions are excluded.
    
    Example:
        paths = ["/path/to/cover1.jpg", "/path/to/cover2.jpg"]
        metadata_list = extract_metadata_batch(paths)
    """
    metadata_list = []
    
    for image_path in image_paths:
        try:
            metadata = extract_metadata(image_path)
            metadata_list.append(metadata)
        except MetadataExtractionError as e:
            logger.warning(f"Skipping file due to extraction error: {e}")
            continue
    
    logger.info(f"Batch extraction complete: {len(metadata_list)}/{len(list(image_paths))} files processed")
    
    return metadata_list
