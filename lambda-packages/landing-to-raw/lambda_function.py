"""
Lambda function to AV scan image files in the landing bucket and promote clean files to raw.

Triggered by S3 ObjectCreated events on landing/uploads/{user_id}/{upload_id}/{filename}.
Reads the file bytes, runs an AV scan, and on a clean result copies to the raw bucket
and triggers the enrichment Step Functions state machine. Infected files are deleted from
landing and the upload is marked as failed.
"""

import json
import os
from typing import Any

import boto3
import scanner
from common.handler import BaseS3BatchHandler
from common.s3 import parse_upload_key, resolve_bucket
from common.tracker import BookshelfTracker, UploadStage


class LandingToRawHandler(BaseS3BatchHandler):
    """AV scans landing-bucket uploads and promotes clean files to raw."""

    def __init__(
        self,
        s3_client: Any = None,
        tracker: Any = None,
        stepfunctions_client: Any = None,
    ) -> None:
        super().__init__(s3_client)

        raw_bucket = os.environ.get("RAW_BUCKET", "")
        if not raw_bucket:
            raise ValueError("RAW_BUCKET environment variable is required")
        self._raw_bucket_tier = raw_bucket

        state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")
        if not state_machine_arn:
            raise ValueError("STATE_MACHINE_ARN environment variable is required")
        self._state_machine_arn = state_machine_arn

        if tracker is not None:
            self._tracker = tracker
        else:
            tracking_table = os.environ.get("TRACKING_TABLE", "")
            if not tracking_table:
                raise ValueError("TRACKING_TABLE environment variable is required")
            self._tracker = BookshelfTracker(table_name=tracking_table)

        self._stepfunctions_client = stepfunctions_client or boto3.client("stepfunctions")

    def process_record(self, bucket: str, key: str) -> str:
        user_id, upload_id, filename = parse_upload_key(key)
        raw_bucket = resolve_bucket(bucket, self._raw_bucket_tier)

        self._tracker.create_record(user_id, upload_id, filename, bucket, key)
        self._tracker.start_stage(user_id, upload_id, filename, UploadStage.AV_SCAN, bucket, key)

        data = self.s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
        clean = scanner.scan(data)

        if not clean:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            self._tracker.fail_stage(
                user_id,
                upload_id,
                filename,
                UploadStage.AV_SCAN,
                "AV scan failed: file quarantined",
            )
            raise ValueError("AV scan failed: file quarantined")

        self.s3_client.copy_object(
            CopySource={"Bucket": bucket, "Key": key},
            Bucket=raw_bucket,
            Key=key,
        )
        self._tracker.complete_stage(
            user_id, upload_id, filename, UploadStage.AV_SCAN, raw_bucket, key
        )
        self._stepfunctions_client.start_execution(
            stateMachineArn=self._state_machine_arn,
            input=json.dumps({"bucket": raw_bucket, "key": key}),
        )

        self.logger.info(f"Promoted s3://{bucket}/{key} to s3://{raw_bucket}/{key}")
        return key


handler = LandingToRawHandler()
