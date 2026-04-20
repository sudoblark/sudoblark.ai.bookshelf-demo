"""Lambda handler for embedding generation.

Invoked by the embedding Step Functions state machine with:
    {"upload_id": "<uuid>"}

Steps
-----
1. Read the tracking record to find the ENRICHMENT destination S3 key.
2. Fetch the metadata JSON from S3.
3. Call Bedrock Titan to generate a text embedding.
4. Write the embedding as ``<metadata_key>.embedding.json`` in the raw bucket.
5. Record an EMBEDDING stage entry in the tracking table (start + complete).

The handler is idempotent — re-running for the same upload_id will overwrite
the existing embedding file.

Environment variables
---------------------
RAW_BUCKET             S3 bucket holding metadata and embedding JSON files.
TRACKING_TABLE         DynamoDB table name for the ingestion tracker.
EMBEDDING_MODEL_ID     Bedrock model ID (default: amazon.titan-embed-text-v1).
BEDROCK_REGION         AWS region for Bedrock calls (default: eu-west-2).
LOG_LEVEL              Python log level (default: INFO).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from common.tracker import BookshelfTracker, StageStatus, UploadStage

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _get_clients() -> tuple:
    s3 = boto3.client("s3")
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("BEDROCK_REGION", "eu-west-2"),
    )
    dynamodb = boto3.resource("dynamodb")
    return s3, bedrock, dynamodb


def _find_metadata_key(record: dict) -> Optional[str]:
    """Return the S3 key from the most recent successful ENRICHMENT stage."""
    for stage in reversed(record.get("stage_progress", [])):
        if (
            stage.get("stage_name") == UploadStage.ENRICHMENT.value
            and stage.get("status") == StageStatus.SUCCESS.value
        ):
            dest = stage.get("destination") or {}
            return dest.get("key")
    return None


def _generate_embedding(
    bedrock: Any,
    model_id: str,
    text: str,
) -> Optional[List[float]]:
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        return json.loads(response["body"].read())["embedding"]
    except Exception:
        logger.warning("Failed to generate embedding for text: %s...", text[:50])
        return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Step Functions entry point.

    Args:
        event: Must contain ``upload_id`` (str).
        context: Lambda context (unused).

    Returns:
        Dict with ``upload_id`` and ``embedding_key`` on success.

    Raises:
        ValueError: If upload_id is missing or no tracking record is found.
        RuntimeError: If embedding generation fails.
    """
    upload_id: str = event.get("upload_id", "")
    if not upload_id:
        raise ValueError("upload_id is required in event payload")

    raw_bucket: str = os.environ["RAW_BUCKET"]
    tracking_table: str = os.environ["TRACKING_TABLE"]
    model_id: str = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")

    s3, bedrock, dynamodb = _get_clients()
    tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=tracking_table)

    record = tracker.get_by_id(upload_id)
    if not record:
        raise ValueError(f"No tracking record found for upload_id={upload_id}")

    metadata_key = _find_metadata_key(record)
    if not metadata_key:
        raise ValueError(f"No successful ENRICHMENT stage found for upload_id={upload_id}")

    # Fetch the metadata JSON to build embedding text
    response = s3.get_object(Bucket=raw_bucket, Key=metadata_key)
    metadata = json.loads(response["Body"].read())

    embedding_text = str(
        metadata.get("description")
        or f"{metadata.get('title', '')} by {metadata.get('author', '')}"
    )

    # Record EMBEDDING stage start
    tracker.start_stage(
        upload_id=upload_id,
        stage=UploadStage.EMBEDDING,
        source_bucket=raw_bucket,
        source_key=metadata_key,
    )

    embedding = _generate_embedding(bedrock, model_id, embedding_text)
    if embedding is None:
        tracker.fail_stage(
            user_id="system",
            upload_id=upload_id,
            stage=UploadStage.EMBEDDING,
            error_message="Bedrock embedding generation returned None",
        )
        raise RuntimeError(f"Embedding generation failed for upload_id={upload_id}")

    embedding_key = metadata_key.replace(".json", ".embedding.json")
    s3.put_object(
        Bucket=raw_bucket,
        Key=embedding_key,
        Body=json.dumps({"upload_id": upload_id, "embedding": embedding}).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Saved embedding to s3://%s/%s", raw_bucket, embedding_key)

    tracker.complete_stage(
        user_id="system",
        upload_id=upload_id,
        stage=UploadStage.EMBEDDING,
        dest_bucket=raw_bucket,
        dest_key=embedding_key,
    )

    return {"upload_id": upload_id, "embedding_key": embedding_key}
