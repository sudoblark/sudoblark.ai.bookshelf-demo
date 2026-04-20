"""Tests for common.tracker — BookshelfTracker DynamoDB helper."""

import boto3
import pytest
from common.tracker import BookshelfTracker, UploadStage
from moto import mock_aws

TABLE_NAME = "test-ingestion-tracking"
USER_ID = "user-123"
UPLOAD_ID = "upload-abc"
FILENAME = "cover.jpg"
LANDING_BUCKET = "landing"
LANDING_KEY = f"uploads/{USER_ID}/{UPLOAD_ID}/{FILENAME}"
RAW_BUCKET = "raw"
RAW_KEY = f"uploads/{USER_ID}/{UPLOAD_ID}/{FILENAME}"


@pytest.fixture
def dynamodb_resource(aws_credentials):
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-west-2")
        resource.create_table(
            TableName=TABLE_NAME,
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
        yield resource


@pytest.fixture
def tracker(dynamodb_resource):
    return BookshelfTracker(dynamodb_resource=dynamodb_resource, table_name=TABLE_NAME)


def _get_item(dynamodb_resource):
    table = dynamodb_resource.Table(TABLE_NAME)
    return table.get_item(Key={"upload_id": UPLOAD_ID}).get("Item")


class TestCreateRecord:
    def test_creates_item_with_correct_keys(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert item is not None
        assert item["upload_id"] == UPLOAD_ID
        assert item["user_id"] == USER_ID

    def test_initial_stage_is_queued(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert item["stage"] == "queued"

    def test_stages_is_empty_dict(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert item["stages"] == {}

    def test_timestamps_are_set(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert "created_at" in item
        assert "updated_at" in item


class TestStartStage:
    def test_writes_stage_entry_to_dict(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        item = _get_item(dynamodb_resource)
        assert "routing" in item["stages"]

    def test_stage_entry_has_correct_fields(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        item = _get_item(dynamodb_resource)
        entry = item["stages"]["routing"]
        assert entry["sourceBucket"] == LANDING_BUCKET
        assert entry["sourceKey"] == LANDING_KEY
        assert entry["destinationBucket"] is None
        assert entry["destinationKey"] is None
        assert "startedAt" in entry

    def test_multiple_stages_stored_in_dict(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        tracker.start_stage(UPLOAD_ID, UploadStage.ANALYSED, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert "routing" in item["stages"]
        assert "analysed" in item["stages"]


class TestCompleteStage:
    def test_sets_stage_field(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert item["stage"] == "routing"

    def test_sets_destination_fields(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        entry = item["stages"]["routing"]
        assert entry["destinationBucket"] == RAW_BUCKET
        assert entry["destinationKey"] == RAW_KEY

    def test_sets_ended_at(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert item["stages"]["routing"]["endedAt"] is not None


class TestFailStage:
    def test_sets_stage_field_to_failed(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stage"] == "failed"

    def test_sets_error_field(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stages"]["routing"]["error"] == "Copy failed"

    def test_sets_ended_at(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stages"]["routing"]["endedAt"] is not None
