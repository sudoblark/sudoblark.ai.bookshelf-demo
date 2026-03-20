"""
Lambda function to extract book metadata from images using AWS Bedrock.

This function is triggered by S3 ObjectCreated events on the raw bucket
and uses Claude 3 Haiku via AWS Bedrock to extract book metadata from
images, then writes the results to Parquet format in the processed bucket.
"""

import logging
import os
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source
from bedrock_extractor import BedrockMetadataExtractor  # noqa: F401
from config import Config
from image_processor import ImageProcessor  # noqa: F401
from parquet_writer import ParquetWriter  # noqa: F401
from processor import BookshelfProcessor

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Module-level clients for connection reuse across Lambda invocations
_s3_client = boto3.client("s3")
_bedrock_client = boto3.client("bedrock-runtime")


@event_source(data_class=S3Event)
def handler(event: S3Event, context: Any) -> Dict[str, Any]:
    """Lambda handler to process S3 events and extract metadata from images.

    Returns:
        Response with statusCode (200 or 207), processed/failed counts, and file details.
    """
    logger.info("Received S3 event for processing")

    try:
        config: Config = Config.from_env()
        processor = BookshelfProcessor(
            config=config,
            s3_client=_s3_client,
            bedrock_client=_bedrock_client,
        )

        processed_files: List[str] = []
        failed_files: List[Dict[str, str]] = []

        for record in event.records:
            try:
                bucket_name: str = record.s3.bucket.name
                object_key: str = record.s3.get_object.key

                if ".." in object_key:
                    raise ValueError(f"Invalid S3 key (path traversal): {object_key}")

                logger.info(f"Processing image: s3://{bucket_name}/{object_key}")

                parquet_key: str = processor.process(bucket_name, object_key)
                processed_files.append(parquet_key)

            except Exception as e:
                logger.error(f"Failed to process record: {str(e)}", exc_info=True)
                failed_files.append({"key": record.s3.get_object.key, "error": str(e)})

        response: Dict[str, Any] = {
            "statusCode": 200 if not failed_files else 207,
            "processed_count": len(processed_files),
            "failed_count": len(failed_files),
            "processed_files": processed_files,
            "failed_files": failed_files,
        }

        logger.info(f"Processing complete: {response}")
        return response

    except Exception as e:
        logger.error(f"Handler execution failed: {str(e)}", exc_info=True)
        raise
