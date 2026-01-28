"""
Processor configuration for the Bookshelf Demo ETL pipeline.

Holds constants used by the processor. Values can be overridden by
environment variables for demo configuration.
"""
import os
from pathlib import Path

# Project layout
PROCESSOR_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = PROCESSOR_DIR.parent

# Data directories (shared with backend)
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Ensure directories exist
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Number of records to accumulate before writing Parquet.
# Default to 1 for demos (flush immediately). Can be overridden via
# the PROCESSOR_BATCH_SIZE environment variable.
PROCESSOR_BATCH_SIZE = int(os.getenv('PROCESSOR_BATCH_SIZE', '1'))

def get_config() -> dict:
    return {
        'DATA_RAW_DIR': str(DATA_RAW_DIR),
        'DATA_PROCESSED_DIR': str(DATA_PROCESSED_DIR),
        'PROCESSOR_BATCH_SIZE': PROCESSOR_BATCH_SIZE,
    }
