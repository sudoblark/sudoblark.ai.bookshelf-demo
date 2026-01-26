
"""
Filesystem watcher module for monitoring new image files.

This module uses the watchdog library to monitor the data/raw directory
for new image file events. When a new image is detected, a callback
function is invoked to pass the file to the extraction pipeline.

Design:
- Single responsibility: detect and report filesystem events
- Uses event-driven architecture via watchdog
- Filters for image file extensions only
- Debounces rapid changes to prevent duplicate processing
"""

import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from logger import get_logger

logger = get_logger(__name__)


# Supported image file extensions (case-insensitive)
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}


class ImageFileHandler(FileSystemEventHandler):
    """
    Handler for filesystem events.
    
    Processes file creation events and forwards image files
    to the provided callback function.
    """

    def __init__(self, callback, data_raw_path):
        """
        Initialize the handler.
        
        Args:
            callback: Function to call when a new image is detected.
                     Receives the absolute file path as argument.
            data_raw_path: Absolute path to the data/raw directory.
        """
        super().__init__()
        self.callback = callback
        self.data_raw_path = Path(data_raw_path).resolve()
        # Track recently processed files to debounce events
        self._processed_files = set()

    def on_created(self, event):
        """
        Handle file creation events.
        
        Filters for image files and invokes the callback.
        
        Args:
            event: FileSystemEventHandler event object.
        """
        # Ignore directories
        if event.is_directory:
            return

        file_path = Path(event.src_path).resolve()

        # Check if file is in the monitored directory
        try:
            file_path.relative_to(self.data_raw_path)
        except ValueError:
            # File is not in the watched directory
            return

        # Check if file has a supported extension
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.debug(f"Ignoring file with unsupported extension: {file_path}")
            return

        # Debounce: skip if we've recently processed this file
        file_key = str(file_path)
        if file_key in self._processed_files:
            logger.debug(f"Debouncing duplicate event for: {file_path}")
            return

        # Mark file as processed
        self._processed_files.add(file_key)

        # Check if file exists and is readable (handles race conditions)
        if not file_path.exists():
            logger.warning(f"File created event but file no longer exists: {file_path}")
            self._processed_files.discard(file_key)
            return

        # Log the detected file
        logger.info(f"New image detected: {file_path}")

        # Invoke callback with the file path
        try:
            self.callback(str(file_path))
        except Exception as e:
            # Log but don't fail—allow continued processing
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
        finally:
            # Remove from debounce set after processing
            self._processed_files.discard(file_key)


class FileWatcher:
    """
    Monitors the data/raw directory for new image files.
    
    Uses watchdog to detect filesystem events and invoke callbacks
    when new images arrive. This class manages the observer lifecycle.
    """

    def __init__(self, data_raw_path, on_image_created):
        """
        Initialize the file watcher.
        
        Args:
            data_raw_path: Path to the data/raw directory.
                          Can be relative or absolute.
            on_image_created: Callback function to invoke when a new image
                            is detected. Receives the absolute file path.
        """
        self.data_raw_path = Path(data_raw_path).resolve()
        self.on_image_created = on_image_created
        
        # Ensure the directory exists
        self.data_raw_path.mkdir(parents=True, exist_ok=True)
        
        # Create event handler and observer
        self.event_handler = ImageFileHandler(
            callback=self.on_image_created,
            data_raw_path=self.data_raw_path
        )
        self.observer = Observer()

    def start(self):
        """
        Start watching the data/raw directory.
        
        Begins monitoring filesystem events. This method is non-blocking
        and runs in a background thread via watchdog.
        """
        # Schedule the observer to watch the directory
        self.observer.schedule(
            self.event_handler,
            path=str(self.data_raw_path),
            recursive=False  # Only monitor the top-level directory
        )
        self.observer.start()
        logger.info(f"File watcher started, monitoring: {self.data_raw_path}")

    def stop(self):
        """
        Stop watching the data/raw directory.
        
        Gracefully shuts down the observer and waits for cleanup.
        """
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped.")


def create_watcher(data_raw_path, on_image_created):
    """
    Factory function to create and configure a FileWatcher.
    
    Args:
        data_raw_path: Path to the data/raw directory.
        on_image_created: Callback function for new images.
    
    Returns:
        FileWatcher instance.
    """
    return FileWatcher(data_raw_path, on_image_created)