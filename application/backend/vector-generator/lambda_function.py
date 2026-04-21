"""Lambda handler for generating Bedrock Titan text embeddings.

Invoked by the enrichment Step Functions state machine with:
    {"upload_id": "<uuid>"}

Steps
-----
1. Read the tracking record to find the PROCESSED stage destination S3 key.
2. Fetch the metadata JSON from the processed bucket.
3. Call Bedrock Titan to generate a text embedding.
4. Write the embedding as ``<metadata_key>.embedding.json`` in the processed bucket.
5. Record an EMBEDDING stage entry in the tracking table (start + complete).

The handler is idempotent — re-running for the same upload_id will overwrite
the existing embedding file.

Environment variables
---------------------
PROCESSED_BUCKET   S3 bucket holding processed metadata and embedding JSON files.
TRACKING_TABLE     DynamoDB table name for the ingestion tracker.
EMBEDDING_MODEL_ID Bedrock model ID (default: amazon.titan-embed-text-v1).
BEDROCK_REGION     AWS region for Bedrock calls (default: eu-west-2).
LOG_LEVEL          Python log level (default: INFO).
"""

import json
import os
from typing import Any, Dict, List, Optional

import boto3
from common.handler import BaseStepFunctionsProcessor
from common.tracker import UploadStage


class VectorGeneratorProcessor(BaseStepFunctionsProcessor):
    def __init__(self, s3_client=None, dynamodb_resource=None, bedrock_client=None):
        super().__init__(s3_client=s3_client, dynamodb_resource=dynamodb_resource)
        self._processed_bucket: str = os.environ["PROCESSED_BUCKET"]
        self._model_id: str = os.environ.get("EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")
        self._bedrock = bedrock_client or boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("BEDROCK_REGION", "eu-west-2"),
        )

    def _find_processed_key(self, record: dict) -> Optional[str]:
        stages = record.get("stages") or {}
        processed = stages.get(UploadStage.PROCESSED.value) or {}
        return processed.get("destinationKey")

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        try:
            response = self._bedrock.invoke_model(
                modelId=self._model_id,
                body=json.dumps({"inputText": text}),
                contentType="application/json",
                accept="application/json",
            )
            return json.loads(response["body"].read())["embedding"]
        except Exception:
            self.logger.exception("Failed to generate embedding for text: %s...", text[:50])
            return None

    def process(self, upload_id: str, record: dict) -> Dict[str, Any]:
        processed_key = self._find_processed_key(record)
        if not processed_key:
            raise ValueError(f"No completed PROCESSED stage found for upload_id={upload_id}")

        response = self.s3_client.get_object(Bucket=self._processed_bucket, Key=processed_key)
        metadata = json.loads(response["Body"].read())

        embedding_text = str(
            metadata.get("description")
            or f"{metadata.get('title', '')} by {metadata.get('author', '')}"
        )

        self.tracker.start_stage(
            upload_id=upload_id,
            stage=UploadStage.EMBEDDING,
            source_bucket=self._processed_bucket,
            source_key=processed_key,
        )

        embedding = self._generate_embedding(embedding_text)
        if embedding is None:
            self.tracker.fail_stage(
                user_id="system",
                upload_id=upload_id,
                stage=UploadStage.EMBEDDING,
                error_message="Bedrock embedding generation returned None",
            )
            raise RuntimeError(f"Embedding generation failed for upload_id={upload_id}")

        embedding_key = processed_key.replace(".json", ".embedding.json")
        self.s3_client.put_object(
            Bucket=self._processed_bucket,
            Key=embedding_key,
            Body=json.dumps({"upload_id": upload_id, "embedding": embedding}).encode("utf-8"),
            ContentType="application/json",
        )
        self.logger.info("Saved embedding to s3://%s/%s", self._processed_bucket, embedding_key)

        self.tracker.complete_stage(
            user_id="system",
            upload_id=upload_id,
            stage=UploadStage.EMBEDDING,
            dest_bucket=self._processed_bucket,
            dest_key=embedding_key,
        )

        return {"upload_id": upload_id, "embedding_key": embedding_key}


_processor = VectorGeneratorProcessor(
    s3_client=boto3.client("s3"),
    dynamodb_resource=boto3.resource("dynamodb"),
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    return _processor(event, context)
