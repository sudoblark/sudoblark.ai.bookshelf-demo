"""Abstract base processors for Lambda functions.

``BaseDataProcessor``
    Provides shared plumbing for S3-triggered Lambdas that process a batch of
    ObjectCreated records:

    - A :class:`~common.data_lake.BookshelfDataLake` instance exposing all bucket
      tier names, constructed from the ``DATA_LAKE_PREFIX`` environment variable.
    - A logger keyed to the concrete class name, level controlled by ``LOG_LEVEL``.
    - A ``boto3`` S3 client (injectable for tests).
    - A ``__call__`` implementation that parses the S3 event, validates each key,
      dispatches to ``process_record``, and returns a standardised batch response.

    Subclasses must implement ``process_record``.

``BaseStepFunctionsProcessor``
    Provides shared plumbing for Step Functions-triggered Lambdas that receive
    ``{"upload_id": "<uuid>"}`` events:

    - A logger keyed to the concrete class name, level controlled by ``LOG_LEVEL``.
    - A ``boto3`` S3 client and DynamoDB resource (injectable for tests).
    - A :class:`~common.tracker.BookshelfTracker` instance constructed from
      the ``TRACKING_TABLE`` environment variable.
    - A ``__call__`` implementation that validates the upload_id, retrieves the
      tracking record, and dispatches to ``process``.

    Subclasses must implement ``process``.

Usage::

    from common.handler import BaseDataProcessor, BaseStepFunctionsProcessor

    class MyProcessor(BaseDataProcessor):
        def process_record(self, key: str) -> str:
            data = self.s3_client.get_object(Bucket=self.data_lake.raw, Key=key)
            ...
            return output_key

    handler = MyProcessor()   # Lambda entry point

    class MyEnrichmentProcessor(BaseStepFunctionsProcessor):
        def process(self, upload_id: str, record: dict) -> dict:
            ...
            return {"upload_id": upload_id, "result_key": "..."}

    handler = MyEnrichmentProcessor()   # Lambda entry point
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import boto3
from common.data_lake import BookshelfDataLake
from common.response import build_response
from common.s3 import validate_key
from common.tracker import BookshelfTracker


class BaseDataProcessor(ABC):
    """Base processor for Lambda functions that handle batches of S3 ObjectCreated records.

    Args:
        s3_client: boto3 S3 client. Defaults to ``boto3.client("s3")``.
                   Pass a mock in tests.
    """

    def __init__(self, s3_client: Any = None) -> None:
        self.logger = logging.getLogger(type(self).__name__)
        self.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
        self.s3_client: Any = s3_client or boto3.client("s3")

        prefix = os.environ.get("DATA_LAKE_PREFIX", "")
        if not prefix:
            raise ValueError("DATA_LAKE_PREFIX environment variable is required")
        self.data_lake: BookshelfDataLake = BookshelfDataLake.from_prefix(prefix)

    @abstractmethod
    def process_record(self, key: str) -> str:
        """Process a single S3 record.

        Args:
            key: S3 object key (already validated — no path traversal).
                 Use ``self.data_lake`` to resolve the source and destination buckets.

        Returns:
            An output identifier (e.g. destination key) recorded in the response.

        Raises:
            Exception: Any exception is caught by the caller and recorded as a failure.
        """
        ...

    def __call__(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle an S3 event by processing each record and returning a batch response."""
        from aws_lambda_powertools.utilities.data_classes import S3Event

        s3_event = S3Event(event)
        self.logger.info("Received S3 event for processing")

        processed_files: List[str] = []
        failed_files: List[Dict[str, str]] = []

        for record in s3_event.records:
            key: str = record.s3.get_object.key
            try:
                validate_key(key)
                output = self.process_record(key)
                processed_files.append(output)
            except Exception as e:
                self.logger.error(f"Failed to process {key}: {str(e)}", exc_info=True)
                failed_files.append({"key": key, "error": str(e)})

        response = build_response(processed_files, failed_files)
        self.logger.info(f"Processing complete: {response}")
        return response


class BaseStepFunctionsProcessor(ABC):
    """Base processor for Lambda functions driven by Step Functions ``{"upload_id": "..."}`` events.

    Handles the common boilerplate:
    - Validates ``upload_id`` is present in the event.
    - Looks up the DynamoDB tracking record for that upload.
    - Dispatches to :meth:`process` with the upload_id and record.

    Args:
        s3_client: boto3 S3 client. Defaults to ``boto3.client("s3")``.
        dynamodb_resource: boto3 DynamoDB resource. Defaults to ``boto3.resource("dynamodb")``.
    """

    def __init__(self, s3_client: Any = None, dynamodb_resource: Any = None) -> None:
        self.logger = logging.getLogger(type(self).__name__)
        self.logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
        self.s3_client: Any = s3_client or boto3.client("s3")
        dynamodb = dynamodb_resource or boto3.resource("dynamodb")
        tracking_table = os.environ["TRACKING_TABLE"]
        self.tracker: BookshelfTracker = BookshelfTracker(
            dynamodb_resource=dynamodb, table_name=tracking_table
        )

    @abstractmethod
    def process(self, upload_id: str, record: dict) -> Dict[str, Any]:
        """Process a single enrichment step for the given upload.

        Args:
            upload_id: The upload identifier from the Step Functions event.
            record: The full DynamoDB tracking record for the upload.

        Returns:
            A dict that will be passed as output to the next Step Functions state.

        Raises:
            ValueError: For invalid or missing data in the record.
            Exception: Any exception propagates and causes the Step Functions task to fail.
        """
        ...

    def __call__(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle a Step Functions event by validating the upload_id and dispatching to process."""
        upload_id: str = event.get("upload_id", "")
        if not upload_id:
            raise ValueError("upload_id is required in event payload")

        record = self.tracker.get_by_id(upload_id)
        if not record:
            raise ValueError(f"No tracking record found for upload_id={upload_id}")

        self.logger.info("Processing upload_id=%s", upload_id)
        return self.process(upload_id, record)
