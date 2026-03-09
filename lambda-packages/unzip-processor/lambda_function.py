"""
Lambda function to extract image files from ZIP archives in S3.

This function is triggered by S3 ObjectCreated events on the landing bucket
and extracts image files from uploaded ZIP archives to the raw bucket.
"""

import io
import logging
import os
import zipfile
from typing import Any, Dict, List, Tuple

import boto3
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source
from botocore.exceptions import ClientError

# Configure logging
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Initialize S3 client
s3_client = boto3.client("s3")

# Supported image extensions
IMAGE_EXTENSIONS: Tuple[str, ...] = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")


def get_config() -> Dict[str, str]:
    """
    Load and validate configuration from environment variables.

    Returns:
        Dictionary containing validated configuration

    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    raw_bucket: str = os.environ.get("RAW_BUCKET", "")
    if not raw_bucket:
        raise ValueError("RAW_BUCKET environment variable is required")

    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    allowed_levels: List[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in allowed_levels:
        raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")

    return {"raw_bucket": raw_bucket, "log_level": log_level}


@event_source(data_class=S3Event)
def handler(event: S3Event, context: Any) -> Dict[str, Any]:
    """
    Lambda handler to process S3 events and extract ZIP files.

    Args:
        event: S3 event data class from Lambda Powertools
        context: Lambda context object

    Returns:
        Dictionary containing status and processing results with keys:
        - statusCode: HTTP status code (200 or 207)
        - processed_count: Number of files successfully processed
        - failed_count: Number of failures
        - processed_files: List of successfully processed file keys
        - failed_files: List of failed files with error details

    Raises:
        ValueError: If configuration is invalid
        Exception: If processing fails critically
    """
    logger.info("Received S3 event for processing")

    try:
        # Load and validate configuration
        config: Dict[str, str] = get_config()

        processed_files: List[str] = []
        failed_files: List[Dict[str, str]] = []

        # Process each record in the S3 event
        for record in event.records:
            try:
                bucket_name: str = record.s3.bucket.name
                object_key: str = record.s3.get_object.key

                # Validate S3 key for path traversal
                if ".." in object_key:
                    raise ValueError(f"Invalid S3 key (path traversal): {object_key}")

                logger.info(f"Processing ZIP file: s3://{bucket_name}/{object_key}")

                # Extract image files from ZIP
                extracted: List[str] = extract_images_from_zip(
                    bucket_name, object_key, config["raw_bucket"]
                )
                processed_files.extend(extracted)

            except Exception as e:
                logger.error(f"Failed to process record: {str(e)}", exc_info=True)
                failed_files.append({"key": record.s3.get_object.key, "error": str(e)})

        # Prepare response
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


def extract_images_from_zip(source_bucket: str, zip_key: str, raw_bucket_name: str) -> List[str]:
    """
    Download ZIP file from S3, extract image files, and upload to raw bucket.

    Args:
        source_bucket: Source S3 bucket containing the ZIP file
        zip_key: S3 key of the ZIP file
        raw_bucket_name: Short name of destination bucket

    Returns:
        List of extracted image file keys uploaded to raw bucket

    Raises:
        ValueError: If inputs are empty or bucket name format is invalid
        ClientError: If S3 operations fail
        zipfile.BadZipFile: If the file is not a valid ZIP
    """
    # Validate inputs
    if not source_bucket or not zip_key or not raw_bucket_name:
        raise ValueError("source_bucket, zip_key, and raw_bucket_name must not be empty")

    # Resolve full bucket name from source bucket naming pattern
    # Expected format: account-project-application-bucket_type
    # Application name may contain hyphens (e.g., bookshelf-demo)
    # Strategy: Remove the last segment (bucket type), what remains is the prefix
    bucket_parts: List[str] = source_bucket.split("-")
    if len(bucket_parts) < 4:
        raise ValueError(f"Invalid source bucket name format: {source_bucket}")

    # Remove last segment (bucket type like "landing", "raw", "processed")
    # The remaining segments form the prefix: account-project-application
    prefix_parts: List[str] = bucket_parts[:-1]
    prefix: str = "-".join(prefix_parts)
    raw_bucket: str = f"{prefix}-{raw_bucket_name}"

    logger.info(f"Extracting images from s3://{source_bucket}/{zip_key} to s3://{raw_bucket}/")

    try:
        # Download ZIP file from S3
        logger.debug(f"Downloading ZIP file from s3://{source_bucket}/{zip_key}")
        zip_obj: Dict[str, Any] = s3_client.get_object(Bucket=source_bucket, Key=zip_key)
        zip_content: bytes = zip_obj["Body"].read()

        logger.info(f"Downloaded ZIP file: {len(zip_content)} bytes")

        # Extract image files
        image_files: List[Tuple[str, bytes]] = extract_images_from_zip_bytes(zip_content)

        logger.info(f"Found {len(image_files)} image files in ZIP")

        # Upload each image to raw bucket
        uploaded_keys: List[str] = []
        for filename, file_content in image_files:
            try:
                # Sanitize filename to prevent path traversal
                safe_filename: str = os.path.basename(filename)

                logger.debug(f"Uploading image: {safe_filename} ({len(file_content)} bytes)")

                s3_client.put_object(
                    Bucket=raw_bucket,
                    Key=safe_filename,
                    Body=file_content,
                    ContentType=get_content_type(safe_filename),
                )

                uploaded_keys.append(safe_filename)
                logger.debug(f"Uploaded: s3://{raw_bucket}/{safe_filename}")

            except ClientError as e:
                logger.error(f"Failed to upload {filename}: {str(e)}")
                # Continue processing other files
                continue

        logger.info(f"Successfully uploaded {len(uploaded_keys)} image files")
        return uploaded_keys

    except ClientError as e:
        error_code: str = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"S3 operation failed: {error_code}", exc_info=True)
        raise


def extract_images_from_zip_bytes(zip_content: bytes) -> List[Tuple[str, bytes]]:
    """
    Extract image files from ZIP content.

    Args:
        zip_content: ZIP file as bytes

    Returns:
        List of tuples (filename, file_content) for image files only

    Raises:
        zipfile.BadZipFile: If content is not valid ZIP
        ValueError: If zip_content is empty
    """
    if not zip_content:
        raise ValueError("zip_content must not be empty")

    image_files: List[Tuple[str, bytes]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            for name in zf.namelist():
                # Skip directories
                if name.endswith("/"):
                    continue

                # Only extract image files
                if name.lower().endswith(IMAGE_EXTENSIONS):
                    file_data: bytes = zf.read(name)
                    image_files.append((name, file_data))
                    logger.debug(f"Extracted image: {name} ({len(file_data)} bytes)")
                else:
                    logger.debug(f"Skipping non-image file: {name}")

    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {str(e)}")
        raise

    return image_files


def get_content_type(filename: str) -> str:
    """
    Determine Content-Type based on file extension.

    Args:
        filename: Name of the file

    Returns:
        Content-Type string for S3 upload
    """
    extension: str = filename.lower().split(".")[-1]
    content_types: Dict[str, str] = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "webp": "image/webp",
    }
    return content_types.get(extension, "application/octet-stream")
