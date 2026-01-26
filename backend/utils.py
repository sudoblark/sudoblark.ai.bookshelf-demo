
"""
Utility helper functions for the Bookshelf Demo backend.

Provides file validation, safe filename handling, and file discovery
utilities used throughout the backend (routes, parquet_reader).

Design:
- Small, focused functions with single responsibilities
- No Flask dependencies (can be unit tested independently)
- Pure functions where possible (side-effect free)
"""

import os
from pathlib import Path
from typing import List, Optional
import re

from settings import ALLOWED_EXTENSIONS, MAX_FILENAME_LENGTH


def is_allowed_file(filename: str) -> bool:
    """
    Check if a filename has an allowed extension.
    
    Uses the ALLOWED_EXTENSIONS set from settings.py
    to determine if the file is a supported image format.
    
    Args:
        filename: Name of the file to validate (with extension).
    
    Returns:
        True if the file extension is allowed, False otherwise.
    
    Example:
        >>> is_allowed_file("cover.jpg")
        True
        >>> is_allowed_file("document.pdf")
        False
    """
    if not filename or '.' not in filename:
        return False
    
    # Extract file extension and convert to lowercase
    ext = filename.rsplit('.', 1)[1].lower()
    
    return ext in ALLOWED_EXTENSIONS


def safe_filename(filename: str) -> Optional[str]:
    """
    Generate a safe, normalized filename.
    
    Removes directory path components and normalizes the filename
    to prevent path traversal attacks and filesystem issues.
    
    Args:
        filename: The original filename (may contain paths).
    
    Returns:
        Safe normalized filename, or None if invalid.
    
    Example:
        >>> safe_filename("../../../etc/passwd")
        'passwd'
        >>> safe_filename("Cover Book (2024).jpg")
        'Cover Book (2024).jpg'
    """
    if not filename:
        return None
    
    # Remove directory components
    filename = Path(filename).name
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Truncate to max length
    if len(filename) > MAX_FILENAME_LENGTH:
        # Keep extension
        name, ext = os.path.splitext(filename)
        max_name_len = MAX_FILENAME_LENGTH - len(ext)
        filename = name[:max_name_len] + ext
    
    # Verify filename is not empty after sanitization
    if not filename or filename in {'.', '..'}:
        return None
    
    return filename


def list_parquet_files(processed_dir: str) -> List[str]:
    """
    List all Parquet files in a directory.
    
    Searches for files with .parquet extension in the specified directory
    and returns their absolute paths.
    
    Args:
        processed_dir: Path to the directory to search.
    
    Returns:
        List of absolute file paths to Parquet files (sorted by name).
        Empty list if directory doesn't exist or has no Parquet files.
    
    Example:
        >>> files = list_parquet_files("data/processed")
        >>> len(files)
        3
    """
    dir_path = Path(processed_dir)
    
    # Return empty list if directory doesn't exist
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    
    # Find all .parquet files
    parquet_files = sorted(dir_path.glob('*.parquet'))
    
    return [str(f) for f in parquet_files]


def newest_file(file_paths: List[str]) -> Optional[str]:
    """
    Find the newest file by modification time.
    
    Given a list of file paths, returns the one with the most recent
    modification time. Useful for finding the latest processed data.
    
    Args:
        file_paths: List of absolute file paths to check.
    
    Returns:
        Path to the newest file, or None if list is empty or all files
        are inaccessible.
    
    Example:
        >>> files = ["data/output_20260101_120000.parquet", "data/output_20260126_140000.parquet"]
        >>> newest = newest_file(files)
        >>> newest.endswith("20260126_140000.parquet")
        True
    """
    if not file_paths:
        return None
    
    newest = None
    newest_mtime = -1
    
    for filepath in file_paths:
        try:
            # Get modification time
            mtime = os.path.getmtime(filepath)
            
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest = filepath
        except (OSError, FileNotFoundError):
            # Skip files that can't be accessed
            continue
    
    return newest


def validate_filename_input(filename: str) -> bool:
    """
    Validate that a filename input is safe.
    
    Performs comprehensive validation on user-provided filename:
    - Not empty or null
    - Has an allowed extension
    - Can be made safe
    
    Args:
        filename: User-provided filename to validate.
    
    Returns:
        True if filename is valid and safe, False otherwise.
    
    Example:
        >>> validate_filename_input("cover.jpg")
        True
        >>> validate_filename_input("")
        False
    """
    if not filename or not isinstance(filename, str):
        return False
    
    if not is_allowed_file(filename):
        return False
    
    safe = safe_filename(filename)
    if not safe:
        return False
    
    return True
