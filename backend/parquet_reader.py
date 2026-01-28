
"""
Parquet file reader for the Bookshelf Demo backend API.

This module reads and parses Parquet files from the data/processed directory
and converts them into JSON-serializable dictionaries for API responses.

Design:
- Simple interface: read newest Parquet file and return as list of dicts
- Uses pandas and PyArrow for efficient Parquet parsing
- Handles missing, corrupted, or empty files gracefully
- Returns clear error information for debugging
"""

from typing import List, Dict, Tuple, Optional
import pandas as pd

from logger import get_logger
from settings import PROCESSED_DIR
from utils import list_parquet_files, newest_file

logger = get_logger(__name__)


class ParquetReadError(Exception):
    """Raised when Parquet file reading fails."""
    pass


def read_latest_parquet() -> List[Dict[str, any]]:
    """
    Read the newest Parquet file and return records as dictionaries.
    
    Finds the most recently modified Parquet file in the PROCESSED_DIR,
    reads it, and converts to a list of JSON-serializable dictionaries.
    
    Returns:
        List of records (dicts) from the latest Parquet file.
        Empty list if no Parquet files exist yet.
    
    Raises:
        ParquetReadError: If a Parquet file exists but cannot be read.
    
    Example:
        >>> records = read_latest_parquet()
        >>> len(records)
        10
        >>> records[0]['title']
        'Extracted Title'
    """
    logger.debug(f"Attempting to read latest Parquet file from: {PROCESSED_DIR}")
    
    # List all Parquet files in the processed directory
    parquet_files = list_parquet_files(str(PROCESSED_DIR))
    
    if not parquet_files:
        logger.info("No Parquet files found in processed directory")
        return []
    
    # Find the newest file
    latest_file = newest_file(parquet_files)
    
    if not latest_file:
        logger.warning("Parquet files exist but none are readable")
        return []
    
    logger.debug(f"Reading latest Parquet file: {latest_file}")
    
    try:
        # Read Parquet file with pandas
        df = pd.read_parquet(latest_file, engine='pyarrow')
        
        # Convert DataFrame to list of dicts
        records = df.to_dict(orient='records')
        
        logger.info(f"Successfully read {len(records)} records from {latest_file}")
        
        return records
    
    except Exception as e:
        error_msg = f"Failed to read Parquet file {latest_file}: {e}"
        logger.error(error_msg, exc_info=True)
        raise ParquetReadError(error_msg) from e


def read_all_parquet() -> List[Dict[str, any]]:
    """
    Read all Parquet files in the processed directory and return a combined list of records.

    Files that fail to read are skipped with a warning so the API can still return
    any successfully-read records.
    """
    logger.debug(f"Attempting to read all Parquet files from: {PROCESSED_DIR}")

    parquet_files = list_parquet_files(str(PROCESSED_DIR))

    if not parquet_files:
        logger.info("No Parquet files found in processed directory")
        return []

    all_records: List[Dict[str, any]] = []

    for pf in parquet_files:
        try:
            df = pd.read_parquet(pf, engine='pyarrow')
            records = df.to_dict(orient='records')
            all_records.extend(records)
            logger.debug(f"Read {len(records)} records from {pf}")
        except Exception as e:
            logger.warning(f"Failed to read Parquet file {pf}, skipping: {e}")
            continue

    logger.info(f"Successfully aggregated {len(all_records)} records from {len(parquet_files)} Parquet files")
    return all_records


def read_parquet_file(filepath: str) -> List[Dict[str, any]]:
    """
    Read a specific Parquet file and return records as dictionaries.
    
    Args:
        filepath: Absolute path to the Parquet file.
    
    Returns:
        List of records (dicts) from the Parquet file.
    
    Raises:
        ParquetReadError: If the file cannot be read or doesn't exist.
    
    Example:
        >>> records = read_parquet_file("data/processed/output_20260126_120000.parquet")
        >>> len(records)
        5
    """
    logger.debug(f"Reading Parquet file: {filepath}")
    
    try:
        # Read Parquet file with pandas
        df = pd.read_parquet(filepath, engine='pyarrow')
        
        # Convert DataFrame to list of dicts
        records = df.to_dict(orient='records')
        
        logger.info(f"Successfully read {len(records)} records from {filepath}")
        
        return records
    
    except FileNotFoundError as e:
        error_msg = f"Parquet file not found: {filepath}"
        logger.error(error_msg)
        raise ParquetReadError(error_msg) from e
    
    except Exception as e:
        error_msg = f"Failed to read Parquet file {filepath}: {e}"
        logger.error(error_msg, exc_info=True)
        raise ParquetReadError(error_msg) from e


def get_parquet_info() -> Tuple[Optional[str], int, int]:
    """
    Get information about the latest Parquet file.
    
    Returns:
        Tuple of:
        - Latest file path (None if no files)
        - Number of records in latest file
        - Number of columns in latest file
    
    Example:
        >>> path, rows, cols = get_parquet_info()
        >>> print(f"Latest: {path}, {rows} records, {cols} columns")
    """
    logger.debug("Retrieving Parquet file information")
    
    parquet_files = list_parquet_files(str(PROCESSED_DIR))
    
    if not parquet_files:
        logger.info("No Parquet files found")
        return None, 0, 0
    
    latest_file = newest_file(parquet_files)
    
    if not latest_file:
        logger.warning("Parquet files exist but none are readable")
        return None, 0, 0
    
    try:
        # Read Parquet file metadata only (faster than reading full data)
        df = pd.read_parquet(latest_file, engine='pyarrow')
        
        num_records = len(df)
        num_columns = len(df.columns)
        
        logger.debug(f"Parquet info - file: {latest_file}, records: {num_records}, columns: {num_columns}")
        
        return latest_file, num_records, num_columns
    
    except Exception as e:
        logger.error(f"Failed to read Parquet file info: {e}", exc_info=True)
        return latest_file, 0, 0