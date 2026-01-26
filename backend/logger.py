"""
Centralized logging configuration for the Bookshelf Demo backend API.

This module provides a consistent, configurable logging setup used
throughout the backend application. All modules should use get_logger()
to obtain a logger instance.

Configuration:
- Logs are output to both console (INFO level) and file (DEBUG level)
- Format includes timestamp, level, module name, and message
- Log files are written to the backend directory
"""

import logging
import sys
from pathlib import Path


# Log file path (in the backend directory)
LOG_FILE = Path(__file__).parent / "backend.log"

# Logging configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL_CONSOLE = logging.INFO
LOG_LEVEL_FILE = logging.DEBUG


def _setup_root_logger():
    """
    Configure the root logger with console and file handlers.
    
    This is called once at module import time to set up the logging
    infrastructure for the entire backend application.
    """
    root_logger = logging.getLogger()
    
    # Remove any existing handlers (prevents duplicates)
    root_logger.handlers.clear()
    
    # Set root logger level to DEBUG (handlers will filter)
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVEL_CONSOLE)
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (DEBUG level)
    try:
        file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
        file_handler.setLevel(LOG_LEVEL_FILE)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except (IOError, OSError) as e:
        # If file logging fails, log to console but continue
        console_handler.emit(
            logging.LogRecord(
                name="logger",
                level=logging.WARNING,
                pathname="",
                lineno=0,
                msg=f"Failed to set up file logging: {e}",
                args=(),
                exc_info=None
            )
        )


def get_logger(name):
    """
    Get a logger instance for a given module or component.
    
    Args:
        name: The name of the logger, typically __name__ from the calling module.
    
    Returns:
        A configured logging.Logger instance.
    
    Example:
        logger = get_logger(__name__)
        logger.info("API request received")
        logger.error("Failed to read Parquet file")
    """
    return logging.getLogger(name)


# Initialize logging on module import
_setup_root_logger()
