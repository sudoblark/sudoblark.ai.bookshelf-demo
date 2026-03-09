"""
Lambda function to extract book metadata from images using AWS Bedrock.

This function is triggered by S3 ObjectCreated events on the raw bucket
and uses Claude 3 Haiku via AWS Bedrock to extract book metadata from
images, then writes the results to Parquet format in the processed bucket.
"""

import base64
import io
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

import boto3
import pandas as pd
from aws_lambda_powertools.utilities.data_classes import S3Event, event_source
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

# Configure logging
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Initialize AWS clients
s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime")

# Bedrock prompt for metadata extraction
METADATA_EXTRACTION_PROMPT: str = """Extract metadata from this book cover image
and return ONLY a valid JSON object.

CRITICAL: Your response must be ONLY the JSON object - no markdown, no code
blocks, no explanation text.

Required JSON format:
{
  "title": "book title here",
  "author": "author name here",
  "isbn": "digits only, no hyphens",
  "publisher": "publisher name here",
  "published_year": 2024,
  "description": "brief description here"
}

Rules:
- Use double quotes for all strings
- No trailing commas
- isbn: digits only (strip hyphens/spaces), use "" if not found
- published_year: integer (e.g., 2024) or null if not found
- Empty values: use "" for unknown strings, null for unknown year
- Escape special characters in strings (quotes, backslashes, newlines)
- Do not include any text before or after the JSON object

Return ONLY the JSON object."""


def get_config() -> Dict[str, str]:
    """
    Load and validate configuration from environment variables.

    Returns:
        Dictionary containing validated configuration

    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    processed_bucket: str = os.environ.get("PROCESSED_BUCKET", "")
    if not processed_bucket:
        raise ValueError("PROCESSED_BUCKET environment variable is required")

    bedrock_model_id: str = os.environ.get(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )

    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    allowed_levels: List[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in allowed_levels:
        raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")

    return {
        "processed_bucket": processed_bucket,
        "bedrock_model_id": bedrock_model_id,
        "log_level": log_level,
    }


@event_source(data_class=S3Event)
def handler(event: S3Event, context: Any) -> Dict[str, Any]:
    """
    Lambda handler to process S3 events and extract metadata from images.

    Args:
        event: S3 event data class from Lambda Powertools
        context: Lambda context object

    Returns:
        Response dictionary with:
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

                logger.info(f"Processing image: s3://{bucket_name}/{object_key}")

                # Extract metadata and write to Parquet
                parquet_key: str = process_image_to_parquet(bucket_name, object_key, config)
                processed_files.append(parquet_key)

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


def process_image_to_parquet(source_bucket: str, image_key: str, config: Dict[str, str]) -> str:
    """
    Download image, extract metadata using Bedrock, and write to Parquet.

    Args:
        source_bucket: Source S3 bucket containing the image
        image_key: S3 key of the image file
        config: Configuration dictionary

    Returns:
        S3 key of the uploaded Parquet file

    Raises:
        ValueError: If inputs are empty or bucket name format is invalid
        ClientError: If S3 operations fail
    """
    # Validate inputs
    if not source_bucket or not image_key:
        raise ValueError("source_bucket and image_key must not be empty")

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
    processed_bucket: str = f"{prefix}-{config['processed_bucket']}"

    logger.info(f"Extracting metadata from s3://{source_bucket}/{image_key}")

    try:
        # Download image from S3
        image_obj: Dict[str, Any] = s3_client.get_object(Bucket=source_bucket, Key=image_key)
        image_bytes: bytes = image_obj["Body"].read()

        logger.info(f"Downloaded image: {len(image_bytes)} bytes")

        # Extract metadata using Bedrock
        metadata: Dict[str, Any] = extract_metadata_with_bedrock(
            image_bytes, image_key, config["bedrock_model_id"]
        )

        logger.info(f"Extracted metadata: {metadata.get('title', 'Unknown')}")

        # Convert to Parquet and upload
        parquet_key: str = write_metadata_to_parquet(metadata, processed_bucket)

        logger.info(f"Uploaded Parquet file: s3://{processed_bucket}/{parquet_key}")
        return parquet_key

    except ClientError as e:
        error_code: str = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"S3 operation failed: {error_code}", exc_info=True)
        raise


def extract_metadata_with_bedrock(
    image_bytes: bytes, filename: str, model_id: str
) -> Dict[str, Any]:
    """
    Extract book metadata from image using AWS Bedrock.

    Args:
        image_bytes: Image file as bytes
        filename: Original filename
        model_id: Bedrock model ID

    Returns:
        Dictionary with extracted metadata

    Raises:
        ValueError: If image_bytes is empty
        ClientError: If Bedrock API call fails
    """
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")

    try:
        # Resize image for Bedrock
        resized_image_bytes: bytes = resize_image_to_jpeg(image_bytes, max_dim=1024)

        # Encode to base64
        image_base64: str = base64.b64encode(resized_image_bytes).decode("utf-8")

        # Construct Bedrock request
        request_body: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64,
                            },
                        },
                        {"type": "text", "text": METADATA_EXTRACTION_PROMPT},
                    ],
                }
            ],
        }

        logger.debug(f"Calling Bedrock with model: {model_id}")

        # Invoke Bedrock
        response = bedrock_client.invoke_model(modelId=model_id, body=json.dumps(request_body))

        # Parse response
        response_body: Dict[str, Any] = json.loads(response["body"].read())

        if "content" in response_body and len(response_body["content"]) > 0:
            response_text: str = response_body["content"][0]["text"]
            logger.debug(f"Bedrock response: {response_text}")

            # Parse metadata from response
            metadata: Dict[str, Any] = parse_bedrock_response(response_text)
            metadata = ensure_metadata_defaults(metadata, filename)

            logger.info(f"Successfully extracted metadata for: {filename}")
            return metadata

        logger.warning("Unexpected Bedrock response structure")
        raise ValueError("Bedrock response missing content")

    except (ClientError, BotoCoreError) as e:
        logger.error(f"Bedrock API error: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Metadata extraction failed: {str(e)}", exc_info=True)
        raise


def parse_bedrock_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Bedrock model response into metadata dictionary.

    Args:
        response_text: Raw text response from Bedrock

    Returns:
        Dictionary with parsed metadata
    """
    metadata: Dict[str, Any] = {
        "title": "",
        "author": "",
        "publisher": "",
        "description": "",
        "isbn": "",
        "published_year": None,
    }

    try:
        # Try to parse as JSON first
        parsed: Dict[str, Any] = json.loads(response_text.strip())
        for key in metadata.keys():
            if key in parsed:
                metadata[key] = parsed[key]
        logger.debug(f"Successfully parsed JSON response: {metadata}")
        return metadata

    except json.JSONDecodeError:
        logger.warning("Response was not valid JSON, attempting to extract from text")
        logger.debug(f"Response text: {response_text}")

        # Fallback: try to find JSON object in the text
        try:
            start: int = response_text.find("{")
            end: int = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str: str = response_text[start:end]
                parsed = json.loads(json_str)
                for key in metadata.keys():
                    if key in parsed:
                        metadata[key] = parsed[key]
                logger.debug(f"Extracted JSON from text: {metadata}")
                return metadata
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Could not extract JSON from response: {e}")

    return metadata


def resize_image_to_jpeg(image_bytes: bytes, max_dim: int = 1024, quality: int = 90) -> bytes:
    """
    Resize image to fit within max_dim x max_dim and convert to JPEG.

    Args:
        image_bytes: Original image as bytes
        max_dim: Maximum dimension for width/height
        quality: JPEG quality (1-100)

    Returns:
        Resized image as JPEG bytes

    Raises:
        ValueError: If image_bytes is empty
        IOError: If image processing fails
    """
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return buffer.getvalue()

    except Exception as e:
        logger.error(f"Image processing failed: {str(e)}", exc_info=True)
        raise


def ensure_metadata_defaults(metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """
    Ensure metadata has required default fields.

    Args:
        metadata: Metadata dictionary
        filename: Original filename

    Returns:
        Metadata with defaults applied
    """
    if "id" not in metadata or not metadata.get("id"):
        metadata["id"] = str(uuid.uuid4())

    if "filename" not in metadata or not metadata.get("filename"):
        metadata["filename"] = filename

    if "processed_at" not in metadata or not metadata.get("processed_at"):
        metadata["processed_at"] = datetime.utcnow().isoformat() + "Z"

    return metadata


def write_metadata_to_parquet(metadata: Dict[str, Any], processed_bucket: str) -> str:
    """
    Convert metadata to Parquet format and upload to S3.

    Args:
        metadata: Metadata dictionary
        processed_bucket: Full name of processed bucket

    Returns:
        S3 key of uploaded Parquet file

    Raises:
        ValueError: If metadata or bucket is empty
        ClientError: If S3 upload fails
    """
    if not metadata or not processed_bucket:
        raise ValueError("metadata and processed_bucket must not be empty")

    try:
        # Convert metadata to DataFrame
        df = pd.DataFrame([metadata])

        # Generate Parquet key with timestamp
        timestamp: str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        parquet_key: str = f"metadata_{timestamp}_{metadata['id']}.parquet"

        # Write to Parquet bytes
        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False, engine="pyarrow")
        parquet_bytes: bytes = parquet_buffer.getvalue()

        logger.info(f"Generated Parquet file: {len(parquet_bytes)} bytes")

        # Upload to S3
        s3_client.put_object(
            Bucket=processed_bucket,
            Key=parquet_key,
            Body=parquet_bytes,
            ContentType="application/octet-stream",
        )

        logger.info(f"Uploaded Parquet: s3://{processed_bucket}/{parquet_key}")
        return parquet_key

    except Exception as e:
        logger.error(f"Parquet write failed: {str(e)}", exc_info=True)
        raise
