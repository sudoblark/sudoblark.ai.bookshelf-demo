"""Abstract base handler for S3-batch-processing Lambda functions.

``BaseS3BatchHandler``
    Provides shared plumbing for S3-triggered Lambdas that process a batch of
    ObjectCreated records:

    - A logger keyed to the concrete class name, level controlled by ``LOG_LEVEL``.
    - A ``boto3`` S3 client (injectable for tests).
    - A ``__call__`` implementation that parses the S3 event, validates each key,
      dispatches to ``process_record``, and returns a standardised batch response.

    Subclasses must implement ``process_record``.

Usage::

    from common.handler import BaseS3BatchHandler

    class MyHandler(BaseS3BatchHandler):
        def process_record(self, bucket: str, key: str) -> str:
            ...  # do work
            return output_key

    handler = MyHandler()   # Lambda entry point
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools.utilities.data_classes import S3Event
from common.response import build_response
from common.s3 import validate_key


class BaseS3BatchHandler(ABC):
    """Base handler for Lambda functions that process batches of S3 ObjectCreated records.

    Args:
        s3_client: boto3 S3 client. Defaults to ``boto3.client("s3")``.
                   Pass a mock in tests.
    """

    def __init__(self, s3_client: Any = None) -> None:
        self.logger = logging.getLogger(type(self).__name__)
        self.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
        self.s3_client: Any = s3_client or boto3.client("s3")

    @abstractmethod
    def process_record(self, bucket: str, key: str) -> str:
        """Process a single S3 record.

        Args:
            bucket: Name of the S3 bucket containing the object.
            key: S3 object key (already validated — no path traversal).

        Returns:
            An output identifier (e.g. destination key) recorded in the response.

        Raises:
            Exception: Any exception is caught by the caller and recorded as a failure.
        """
        ...

    def __call__(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle an S3 event by processing each record and returning a batch response."""
        s3_event = S3Event(event)
        self.logger.info("Received S3 event for processing")

        processed_files: List[str] = []
        failed_files: List[Dict[str, str]] = []

        for record in s3_event.records:
            key: str = record.s3.get_object.key
            try:
                validate_key(key)
                output = self.process_record(record.s3.bucket.name, key)
                processed_files.append(output)
            except Exception as e:
                self.logger.error(f"Failed to process {key}: {str(e)}", exc_info=True)
                failed_files.append({"key": key, "error": str(e)})

        response = build_response(processed_files, failed_files)
        self.logger.info(f"Processing complete: {response}")
        return response
