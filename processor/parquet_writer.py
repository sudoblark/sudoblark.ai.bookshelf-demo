
"""
Parquet file writer module for persisting metadata.

This module is responsible for converting metadata dictionaries into
Parquet format and writing them to the data/processed directory.
Parquet files are timestamped to avoid collisions and enable
incremental processing.

Design:
- Single responsibility: accumulate metadata and persist to Parquet
- Uses pandas for data manipulation and PyArrow for Parquet serialization
- Timestamped filenames ensure unique outputs
- Supports both single and batch writes
- Includes error handling and validation
"""

from pathlib import Path
from datetime import datetime
import uuid
from typing import Dict, List, Optional
import pandas as pd

from logger import get_logger
import settings as proc_settings

logger = get_logger(__name__)


class ParquetWriteError(Exception):
    """Raised when Parquet file writing fails."""
    pass


class ParquetWriter:
    """
    Writes metadata records to timestamped Parquet files.
    
    Accumulates metadata dictionaries and persists them to the
    data/processed directory as Parquet files with timestamped names.
    """

    def __init__(self, output_dir: str | None = None):
        """
        Initialize the Parquet writer.
        
        Args:
            output_dir: Path to the output directory for Parquet files.
                       Can be relative or absolute. Will be created if missing.
        """
        if output_dir is None:
            output_dir = proc_settings.DATA_PROCESSED_DIR
        self.output_dir = Path(output_dir).resolve()
        
        # Ensure the output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"ParquetWriter initialized with output directory: {self.output_dir}")

    def write(self, metadata_records: List[Dict[str, any]]) -> str:
        """
        Write metadata records to a timestamped Parquet file.
        
        Creates a new Parquet file with a timestamp-based name and writes
        all metadata records to it. Uses pandas DataFrame as intermediate.
        
        Args:
            metadata_records: List of metadata dictionaries to write.
                            Each dict should have consistent keys.
        
        Returns:
            Absolute path to the created Parquet file.
        
        Raises:
            ParquetWriteError: If writing fails.
        
        Example:
            records = [{"title": "Book 1", ...}, {"title": "Book 2", ...}]
            path = writer.write(records)
            print(f"Wrote {len(records)} records to {path}")
        """
        if not metadata_records:
            error_msg = "Cannot write empty metadata records list"
            logger.warning(error_msg)
            raise ParquetWriteError(error_msg)
        
        logger.debug(f"Writing {len(metadata_records)} metadata records to Parquet")

        # Ensure each record has an `id` and `processed_at` for downstream consumers
        for rec in metadata_records:
            if not isinstance(rec, dict):
                continue
            if 'id' not in rec or not rec.get('id'):
                rec['id'] = str(uuid.uuid4())
            if 'processed_at' not in rec or not rec.get('processed_at'):
                rec['processed_at'] = datetime.utcnow().isoformat() + 'Z'
        
        try:
            # Convert list of dicts to pandas DataFrame
            df = pd.DataFrame(metadata_records)
            
            # Generate timestamped filename
            filename = self._generate_timestamped_filename()
            output_path = self.output_dir / filename
            
            # Write to Parquet using PyArrow backend
            df.to_parquet(output_path, engine='pyarrow', index=False)
            
            logger.info(f"Successfully wrote Parquet file: {output_path}")
            logger.debug(f"File contains {len(df)} rows and {len(df.columns)} columns")
            
            return str(output_path)
        
        except Exception as e:
            error_msg = f"Failed to write Parquet file: {e}"
            logger.error(error_msg, exc_info=True)
            raise ParquetWriteError(error_msg) from e

    def write_single(self, metadata: Dict[str, any]) -> str:
        """
        Write a single metadata record to a Parquet file.
        
        Convenience method for writing a single metadata dictionary.
        
        Args:
            metadata: Single metadata dictionary to write.
        
        Returns:
            Absolute path to the created Parquet file.
        
        Raises:
            ParquetWriteError: If writing fails.
        
        Example:
            metadata = {"title": "Book 1", ...}
            path = writer.write_single(metadata)
        """
        # Ensure single metadata record contains required fields
        if 'id' not in metadata or not metadata.get('id'):
            metadata['id'] = str(uuid.uuid4())
        if 'processed_at' not in metadata or not metadata.get('processed_at'):
            metadata['processed_at'] = datetime.utcnow().isoformat() + 'Z'

        return self.write([metadata])

    def _generate_timestamped_filename(self) -> str:
        """
        Generate a unique timestamped filename for Parquet output.
        
        Format: output_YYYYMMDD_HHMMSS.parquet
        
        Returns:
            Filename string with timestamp.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"output_{timestamp}.parquet"
        return filename


def write_metadata_to_parquet(
    metadata_records: List[Dict[str, any]],
    output_dir: str
) -> str:
    """
    Convenience function to write metadata records to a Parquet file.
    
    Creates a ParquetWriter, writes records, and returns the output path.
    
    Args:
        metadata_records: List of metadata dictionaries to write.
        output_dir: Path to the output directory for the Parquet file.
    
    Returns:
        Absolute path to the created Parquet file.
    
    Raises:
        ParquetWriteError: If writing fails.
    
    Example:
        records = [{"title": "Book 1", ...}, {"title": "Book 2", ...}]
        path = write_metadata_to_parquet(records, "data/processed")
    """
    writer = ParquetWriter(output_dir)
    return writer.write(metadata_records)
