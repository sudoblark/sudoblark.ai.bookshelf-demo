
"""
Main entry point for the Bookshelf Demo ETL pipeline.

This module orchestrates the entire workflow:
1. Monitor data/raw for new image files (via watcher)
2. Extract metadata from detected images (via extractor)
3. Accumulate metadata and write Parquet files (via parquet_writer)

Design:
- Simple orchestration that delegates to specialized modules
- Event-driven via the filesystem watcher
- Processes files asynchronously as they arrive
- Graceful shutdown on Ctrl+C
"""

import sys
import signal
from pathlib import Path
from typing import List, Dict, Optional

from logger import get_logger
from watcher import create_watcher
from extractor import extract_metadata, MetadataExtractionError
from parquet_writer import ParquetWriter

logger = get_logger(__name__)


class ETLPipeline:
    """
    Main ETL pipeline orchestrator.
    
    Coordinates the watcher, extractor, and parquet writer to process
    images as they arrive in the data/raw directory and output
    structured Parquet files.
    """

    def __init__(
        self,
        data_raw_dir: str,
        data_processed_dir: str,
        batch_size: int = 1
    ):
        """
        Initialize the ETL pipeline.
        
        Args:
            data_raw_dir: Path to the input directory for raw images.
            data_processed_dir: Path to the output directory for Parquet files.
            batch_size: Number of records to accumulate before writing Parquet.
        """
        self.data_raw_dir = Path(data_raw_dir).resolve()
        self.data_processed_dir = Path(data_processed_dir).resolve()
        self.batch_size = batch_size
        
        # Initialize components
        self.parquet_writer = ParquetWriter(str(self.data_processed_dir))
        self.watcher = create_watcher(str(self.data_raw_dir), self._on_image_detected)
        
        # Metadata accumulator
        self.metadata_buffer: List[Dict[str, any]] = []
        
        logger.info(f"ETL Pipeline initialized")
        logger.debug(f"  Raw directory: {self.data_raw_dir}")
        logger.debug(f"  Processed directory: {self.data_processed_dir}")
        logger.debug(f"  Batch size: {self.batch_size}")

    def _on_image_detected(self, image_path: str) -> None:
        """
        Callback invoked when a new image is detected.
        
        Extracts metadata from the image and accumulates it.
        When batch size is reached, writes a Parquet file.
        
        Args:
            image_path: Absolute path to the detected image file.
        """
        logger.debug(f"Processing image: {image_path}")
        
        try:
            # Extract metadata from the image
            metadata = extract_metadata(image_path)
            
            # Add to buffer
            self.metadata_buffer.append(metadata)
            logger.debug(f"Accumulated {len(self.metadata_buffer)} records in buffer")
            
            # Check if batch size reached
            if len(self.metadata_buffer) >= self.batch_size:
                self._flush_buffer()
        
        except MetadataExtractionError as e:
            logger.error(f"Failed to extract metadata from {image_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing image {image_path}: {e}", exc_info=True)

    def _flush_buffer(self) -> None:
        """
        Write accumulated metadata to a Parquet file.
        
        Clears the buffer after successfully writing.
        """
        if not self.metadata_buffer:
            logger.debug("Buffer is empty, nothing to flush")
            return
        
        try:
            output_path = self.parquet_writer.write(self.metadata_buffer)
            logger.info(f"Flushed {len(self.metadata_buffer)} records to {output_path}")
            self.metadata_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush buffer to Parquet: {e}", exc_info=True)

    def start(self) -> None:
        """
        Start the ETL pipeline.
        
        Begins monitoring the data/raw directory for new images.
        This method blocks until the pipeline is stopped.
        """
        logger.info("Starting ETL pipeline...")
        
        try:
            self.watcher.start()
            
            # Keep the pipeline running
            logger.info("Pipeline running. Press Ctrl+C to stop.")
            signal.pause()  # Wait for signals
        
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self) -> None:
        """
        Stop the ETL pipeline.
        
        Flushes any remaining buffered records and gracefully
        shuts down the filesystem watcher.
        """
        logger.info("Stopping ETL pipeline...")
        
        try:
            # Flush any remaining records
            if self.metadata_buffer:
                logger.info(f"Flushing {len(self.metadata_buffer)} remaining records")
                self._flush_buffer()
            
            # Stop the watcher
            self.watcher.stop()
            logger.info("ETL pipeline stopped successfully")
        
        except Exception as e:
            logger.error(f"Error during pipeline shutdown: {e}", exc_info=True)


def main() -> int:
    """
    Main entry point for the application.
    
    Initializes and runs the ETL pipeline.
    
    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Define data directories
        # Paths are relative to the processor directory
        processor_dir = Path(__file__).parent.resolve()
        project_dir = processor_dir.parent
        data_raw_dir = project_dir / "data" / "raw"
        data_processed_dir = project_dir / "data" / "processed"
        
        logger.info("=" * 60)
        logger.info("Bookshelf Demo ETL Pipeline")
        logger.info("=" * 60)
        
        # Create and run the pipeline
        pipeline = ETLPipeline(
            data_raw_dir=str(data_raw_dir),
            data_processed_dir=str(data_processed_dir),
            batch_size=10
        )
        
        pipeline.start()
        return 0
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
