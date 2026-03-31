"""Tests for landing-to-raw Lambda function."""

import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from common.tracker import BookshelfTracker, StageStatus, UploadStage, UploadStatus
from moto import mock_aws

# Add landing-to-raw directory to sys.path so `import scanner` resolves
LAMBDA_DIR = os.path.join(
    os.path.dirname(__file__), "../application/backend/data-pipeline/landing-to-raw"
)
if LAMBDA_DIR not in sys.path:
    sys.path.insert(0, LAMBDA_DIR)

# Dynamically import lambda_function from landing-to-raw directory
spec = importlib.util.spec_from_file_location(
    "landing_to_raw_lambda_function",
    os.path.join(LAMBDA_DIR, "lambda_function.py"),
)
landing_to_raw_lambda = importlib.util.module_from_spec(spec)
sys.modules["landing_to_raw_lambda_function"] = landing_to_raw_lambda
spec.loader.exec_module(landing_to_raw_lambda)

DATA_LAKE_PREFIX = "aws-sudoblark-development-bookshelf-demo"
LANDING_BUCKET = f"{DATA_LAKE_PREFIX}-landing"
RAW_BUCKET = f"{DATA_LAKE_PREFIX}-raw"
TRACKING_TABLE = "test-tracking"
STATE_MACHINE_ARN = "arn:aws:states:eu-west-2:123456789012:stateMachine:test-raw-to-enriched"
REGION = "eu-west-2"


def _make_s3_event(bucket: str, key: str) -> dict:
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": bucket, "arn": f"arn:aws:s3:::{bucket}"},
                    "object": {"key": key, "size": 100},
                },
            }
        ]
    }


class TestLandingToRawHandlerInit:
    def test_raises_when_data_lake_prefix_missing(self, monkeypatch):
        monkeypatch.delenv("DATA_LAKE_PREFIX", raising=False)
        with pytest.raises(ValueError, match="DATA_LAKE_PREFIX environment variable is required"):
            landing_to_raw_lambda.LandingToRawHandler()

    def test_raises_when_tracking_table_missing(self, monkeypatch):
        monkeypatch.delenv("TRACKING_TABLE", raising=False)
        with pytest.raises(ValueError, match="TRACKING_TABLE environment variable is required"):
            landing_to_raw_lambda.LandingToRawHandler()

    def test_raises_when_state_machine_arn_missing(self, monkeypatch):
        monkeypatch.delenv("STATE_MACHINE_ARN", raising=False)
        with pytest.raises(ValueError, match="STATE_MACHINE_ARN environment variable is required"):
            landing_to_raw_lambda.LandingToRawHandler()


class TestHandlerCleanFile:
    @mock_aws
    def test_copies_file_to_raw_bucket(self, lambda_context):
        mock_sfn = MagicMock()

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=mock_sfn,
        )
        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        assert result["statusCode"] == 200
        assert result["processed_count"] == 1
        assert key in result["processed_files"]

        obj = s3.get_object(Bucket=RAW_BUCKET, Key=key)
        assert obj["Body"].read() == b"imgdata"

    @mock_aws
    def test_does_not_delete_source_from_landing(self, lambda_context):
        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=MagicMock(),
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        obj = s3.get_object(Bucket=LANDING_BUCKET, Key=key)
        assert obj["Body"].read() == b"imgdata"

    @mock_aws
    def test_calls_start_execution_with_correct_payload(self, lambda_context):
        mock_sfn = MagicMock()

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=mock_sfn,
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        mock_sfn.start_execution.assert_called_once_with(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps({"upload_id": "test-upload", "bucket": RAW_BUCKET, "key": key}),
        )

    @mock_aws
    def test_complete_stage_called(self, lambda_context):
        mock_tracker = MagicMock()

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=mock_tracker,
            stepfunctions_client=MagicMock(),
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        mock_tracker.complete_stage.assert_called_once()
        call_args = mock_tracker.complete_stage.call_args
        assert call_args.args[2] == UploadStage.AV_SCAN


class TestHandlerInfectedFile:
    @mock_aws
    def test_deletes_source_from_landing(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=MagicMock(),
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        objects = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix="uploads/")
        assert objects.get("KeyCount", 0) == 0

    @mock_aws
    def test_does_not_copy_to_raw(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=MagicMock(),
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        objects = s3.list_objects_v2(Bucket=RAW_BUCKET)
        assert objects.get("KeyCount", 0) == 0

    @mock_aws
    def test_calls_fail_stage(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)
        mock_tracker = MagicMock()

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=mock_tracker,
            stepfunctions_client=MagicMock(),
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        mock_tracker.fail_stage.assert_called_once()
        call_args = mock_tracker.fail_stage.call_args
        assert call_args.args[2] == UploadStage.AV_SCAN

    @mock_aws
    def test_start_execution_not_called(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)
        mock_sfn = MagicMock()

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=mock_sfn,
        )
        h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        mock_sfn.start_execution.assert_not_called()

    @mock_aws
    def test_returns_207(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )

        key = "uploads/default/test-upload/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=MagicMock(),
            stepfunctions_client=MagicMock(),
        )
        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)

        assert result["statusCode"] == 207
        assert result["failed_count"] == 1


def _create_tracking_table(resource):
    resource.create_table(
        TableName=TRACKING_TABLE,
        KeySchema=[
            {"AttributeName": "upload_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "upload_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user_id-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "upload_id", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


class TestHandlerWithTracking:
    @mock_aws
    def test_records_av_scan_success(self, lambda_context):
        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        key = "uploads/user-1/upload-1/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"imgdata")

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        _create_tracking_table(dynamodb)

        tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=TRACKING_TABLE)
        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=tracker,
            stepfunctions_client=MagicMock(),
        )

        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)
        assert result["statusCode"] == 200

        item = dynamodb.Table(TRACKING_TABLE).get_item(Key={"upload_id": "upload-1"}).get("Item")
        assert item["current_status"] == UploadStatus.SUCCESS.value
        assert len(item["stage_progress"]) == 1
        entry = item["stage_progress"][0]
        assert entry["stage_name"] == UploadStage.AV_SCAN.value
        assert entry["status"] == StageStatus.SUCCESS.value
        assert entry["source"] == {"bucket": LANDING_BUCKET, "key": key}
        assert entry["destination"] == {"bucket": RAW_BUCKET, "key": key}

    @mock_aws
    def test_records_av_scan_failure(self, monkeypatch, lambda_context):
        monkeypatch.setattr(landing_to_raw_lambda.scanner, "scan", lambda data: False)

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (LANDING_BUCKET, RAW_BUCKET):
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        key = "uploads/user-1/upload-1/cover.jpg"
        s3.put_object(Bucket=LANDING_BUCKET, Key=key, Body=b"malware")

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        _create_tracking_table(dynamodb)

        tracker = BookshelfTracker(dynamodb_resource=dynamodb, table_name=TRACKING_TABLE)
        h = landing_to_raw_lambda.LandingToRawHandler(
            s3_client=s3,
            tracker=tracker,
            stepfunctions_client=MagicMock(),
        )

        result = h(_make_s3_event(LANDING_BUCKET, key), lambda_context)
        assert result["statusCode"] == 207

        item = dynamodb.Table(TRACKING_TABLE).get_item(Key={"upload_id": "upload-1"}).get("Item")
        assert item["current_status"] == UploadStatus.FAILED.value
        assert item["stage_progress"][0]["stage_name"] == UploadStage.AV_SCAN.value
        assert item["stage_progress"][0]["status"] == StageStatus.FAILED.value
        assert "quarantined" in item["stage_progress"][0]["error_message"]
