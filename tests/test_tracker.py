"""Tests for common.tracker — BookshelfTracker DynamoDB helper."""

import boto3
import pytest
from common.tracker import BookshelfTracker, StageStatus, UploadStage, UploadStatus
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

    def test_initial_status_is_queued(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert item["current_status"] == UploadStatus.QUEUED.value

    def test_stage_progress_is_empty_list(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"] == []

    def test_timestamps_are_set(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        item = _get_item(dynamodb_resource)
        assert "created_at" in item
        assert "updated_at" in item


class TestStartStage:
    def test_appends_stage_entry(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        item = _get_item(dynamodb_resource)
        assert len(item["stage_progress"]) == 1

    def test_stage_entry_has_correct_fields(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        item = _get_item(dynamodb_resource)
        entry = item["stage_progress"][0]
        assert entry["stage_name"] == UploadStage.ROUTING.value
        assert entry["status"] == StageStatus.IN_PROGRESS.value
        assert entry["source"] == {"bucket": LANDING_BUCKET, "key": LANDING_KEY}
        assert entry["destination"] is None
        assert entry["error_message"] is None

    def test_sets_current_status_to_in_progress(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        item = _get_item(dynamodb_resource)
        assert item["current_status"] == UploadStatus.IN_PROGRESS.value

    def test_multiple_stages_appended_in_order(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        tracker.start_stage(UPLOAD_ID, UploadStage.ENRICHMENT, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert len(item["stage_progress"]) == 2
        assert item["stage_progress"][0]["stage_name"] == UploadStage.ROUTING.value
        assert item["stage_progress"][1]["stage_name"] == UploadStage.ENRICHMENT.value


class TestCompleteStage:
    def test_updates_status_to_success(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"][0]["status"] == StageStatus.SUCCESS.value

    def test_sets_destination(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"][0]["destination"] == {"bucket": RAW_BUCKET, "key": RAW_KEY}

    def test_sets_end_time_and_processing_time(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        entry = item["stage_progress"][0]
        assert entry["end_time"] is not None
        assert float(entry["processing_time"]) >= 0

    def test_sets_upload_current_status_to_success(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        assert item["current_status"] == UploadStatus.SUCCESS.value


class TestFailStage:
    def test_updates_status_to_failed(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"][0]["status"] == StageStatus.FAILED.value

    def test_sets_error_message(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"][0]["error_message"] == "Copy failed"

    def test_sets_upload_current_status_to_failed(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["current_status"] == UploadStatus.FAILED.value

    def test_sets_end_time(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.fail_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, "Copy failed")
        item = _get_item(dynamodb_resource)
        assert item["stage_progress"][0]["end_time"] is not None


class TestFindStageIndex:
    def test_raises_if_stage_progress_is_empty(self, tracker):
        with pytest.raises(ValueError, match="No in-progress entry"):
            tracker._find_stage_index([], UploadStage.ROUTING)

    def test_raises_if_stage_already_completed(self, tracker, dynamodb_resource):
        tracker.create_record(USER_ID, UPLOAD_ID)
        tracker.start_stage(UPLOAD_ID, UploadStage.ROUTING, LANDING_BUCKET, LANDING_KEY)
        tracker.complete_stage(USER_ID, UPLOAD_ID, UploadStage.ROUTING, RAW_BUCKET, RAW_KEY)
        item = _get_item(dynamodb_resource)
        with pytest.raises(ValueError, match="No in-progress entry"):
            tracker._find_stage_index(item["stage_progress"], UploadStage.ROUTING)
