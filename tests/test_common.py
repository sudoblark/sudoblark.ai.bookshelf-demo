"""Tests for lambda-packages/common shared utilities."""

from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from common.data_lake import BookshelfDataLake
from common.handler import BaseDataProcessor
from common.response import build_response
from common.s3 import validate_key
from common.tracker import BookshelfTracker, StageStatus, UploadStage, UploadStatus

# ---------------------------------------------------------------------------
# Minimal concrete implementations used to test BaseDataProcessor directly
# ---------------------------------------------------------------------------


class _IdentityProcessor(BaseDataProcessor):
    """Returns the key unchanged; records each processed key for assertions."""

    def __init__(self, s3_client: Any = None) -> None:
        super().__init__(s3_client)
        self.processed: list = []

    def process_record(self, key: str) -> str:
        self.processed.append(key)
        return key


class _RaisingProcessor(BaseDataProcessor):
    """Always raises from process_record to exercise failure paths."""

    def process_record(self, key: str) -> str:
        raise RuntimeError("processing failed")


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


class TestBookshelfDataLake:
    def test_from_prefix_constructs_all_tiers(self):
        lake = BookshelfDataLake.from_prefix("aws-sudoblark-dev-bookshelf-demo")
        assert lake.landing == "aws-sudoblark-dev-bookshelf-demo-landing"
        assert lake.raw == "aws-sudoblark-dev-bookshelf-demo-raw"
        assert lake.processed == "aws-sudoblark-dev-bookshelf-demo-processed"

    def test_dataclass_attributes_accessible(self):
        lake = BookshelfDataLake(landing="a-landing", raw="a-raw", processed="a-processed")
        assert lake.landing == "a-landing"
        assert lake.raw == "a-raw"
        assert lake.processed == "a-processed"


class TestBaseDataProcessor:
    def test_logger_named_after_concrete_class(self):
        h = _IdentityProcessor(s3_client=MagicMock())
        assert h.logger.name == "_IdentityProcessor"

    def test_data_lake_constructed_from_prefix(self, monkeypatch):
        monkeypatch.setenv("DATA_LAKE_PREFIX", "aws-sudoblark-dev-bookshelf-demo")
        h = _IdentityProcessor(s3_client=MagicMock())
        assert h.data_lake.landing == "aws-sudoblark-dev-bookshelf-demo-landing"
        assert h.data_lake.raw == "aws-sudoblark-dev-bookshelf-demo-raw"
        assert h.data_lake.processed == "aws-sudoblark-dev-bookshelf-demo-processed"

    def test_raises_when_data_lake_prefix_missing(self, monkeypatch):
        monkeypatch.delenv("DATA_LAKE_PREFIX", raising=False)
        with pytest.raises(ValueError, match="DATA_LAKE_PREFIX environment variable is required"):
            _IdentityProcessor(s3_client=MagicMock())

    def test_processes_record_and_returns_200(self):
        h = _IdentityProcessor(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/u/up/cover.jpg"), None)
        assert result["statusCode"] == 200
        assert result["processed_count"] == 1
        assert "uploads/u/up/cover.jpg" in result["processed_files"]

    def test_records_failure_and_returns_207(self):
        h = _RaisingProcessor(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/u/up/cover.jpg"), None)
        assert result["statusCode"] == 207
        assert result["failed_count"] == 1
        assert "processing failed" in result["failed_files"][0]["error"]

    def test_rejects_path_traversal_before_process_record(self):
        h = _IdentityProcessor(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/../secret/file.jpg"), None)
        assert result["statusCode"] == 207
        assert len(h.processed) == 0  # process_record was never called


class TestValidateKey:
    def test_valid_key_passes(self):
        validate_key("uploads/default/test-upload/cover.jpg")  # should not raise

    def test_path_traversal_raises(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_key("uploads/../secret/file.jpg")

    def test_double_dot_in_filename_raises(self):
        with pytest.raises(ValueError, match="path traversal"):
            validate_key("uploads/default/upload1/fi..le.jpg")

    def test_empty_key_passes(self):
        validate_key("")  # no '..' present, should not raise


class TestBuildResponse:
    def test_returns_200_when_no_failures(self):
        response = build_response(["a.jpg", "b.jpg"], [])
        assert response["statusCode"] == 200
        assert response["processed_count"] == 2
        assert response["failed_count"] == 0
        assert response["processed_files"] == ["a.jpg", "b.jpg"]
        assert response["failed_files"] == []

    def test_returns_207_when_failures_present(self):
        response = build_response(["a.jpg"], [{"key": "b.jpg", "error": "oops"}])
        assert response["statusCode"] == 207
        assert response["processed_count"] == 1
        assert response["failed_count"] == 1

    def test_returns_207_when_all_failed(self):
        failed = [{"key": "a.jpg", "error": "boom"}]
        response = build_response([], failed)
        assert response["statusCode"] == 207
        assert response["processed_count"] == 0
        assert response["failed_count"] == 1

    def test_empty_returns_200(self):
        response = build_response([], [])
        assert response["statusCode"] == 200
        assert response["processed_count"] == 0
        assert response["failed_count"] == 0


# ---------------------------------------------------------------------------
# BookshelfTracker
# ---------------------------------------------------------------------------

_IN_PROGRESS_ROUTING = {
    "stage_name": UploadStage.ROUTING.value,
    "status": StageStatus.IN_PROGRESS.value,
    "start_time": "2026-01-01T00:00:00+00:00",
    "end_time": None,
    "processing_time": None,
    "source": {"bucket": "landing-bucket", "key": "uploads/u/up/book.zip"},
    "destination": None,
    "error_message": None,
}


def _make_tracker(item: Optional[dict] = None):
    """Return a (BookshelfTracker, mock_table) pair."""
    mock_resource = MagicMock()
    mock_table = MagicMock()
    mock_resource.Table.return_value = mock_table
    if item is not None:
        mock_table.get_item.return_value = {"Item": item}
    return BookshelfTracker(dynamodb_resource=mock_resource, table_name="test-table"), mock_table


class TestBookshelfTracker:
    def test_create_record_puts_item_with_queued_status(self):
        tracker, table = _make_tracker()
        tracker.create_record("u1", "up1")
        table.put_item.assert_called_once()
        item = table.put_item.call_args[1]["Item"]
        assert item["user_id"] == "u1"
        assert item["upload_id"] == "up1"
        assert item["current_status"] == UploadStatus.QUEUED.value
        assert item["stage_progress"] == []

    def test_start_stage_appends_entry_and_sets_in_progress(self):
        tracker, table = _make_tracker()
        tracker.start_stage("up1", UploadStage.ROUTING, "landing", "uploads/u1/up1/book.zip")
        table.update_item.assert_called_once()
        vals = table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert vals[":status"] == UploadStatus.IN_PROGRESS.value
        assert len(vals[":entry"]) == 1
        assert vals[":entry"][0]["stage_name"] == UploadStage.ROUTING.value
        assert vals[":entry"][0]["status"] == StageStatus.IN_PROGRESS.value

    def test_complete_stage_marks_success(self):
        tracker, table = _make_tracker({"stage_progress": [dict(_IN_PROGRESS_ROUTING)]})
        tracker.complete_stage(
            "u1", "up1", UploadStage.ROUTING, "raw-bucket", "raw/u1/up1/book.zip"
        )
        table.update_item.assert_called_once()
        vals = table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert vals[":status"] == UploadStatus.SUCCESS.value
        assert vals[":entry"]["status"] == StageStatus.SUCCESS.value
        assert vals[":entry"]["destination"] == {
            "bucket": "raw-bucket",
            "key": "raw/u1/up1/book.zip",
        }

    def test_fail_stage_marks_failed_with_error_message(self):
        tracker, table = _make_tracker({"stage_progress": [dict(_IN_PROGRESS_ROUTING)]})
        tracker.fail_stage("u1", "up1", UploadStage.ROUTING, "something went wrong")
        table.update_item.assert_called_once()
        vals = table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert vals[":status"] == UploadStatus.FAILED.value
        assert vals[":entry"]["status"] == StageStatus.FAILED.value
        assert vals[":entry"]["error_message"] == "something went wrong"

    def test_complete_stage_selects_last_in_progress_entry(self):
        """When two routing entries exist, the most recent in-progress one is updated."""
        completed_entry = {**_IN_PROGRESS_ROUTING, "status": StageStatus.SUCCESS.value}
        tracker, table = _make_tracker(
            {"stage_progress": [completed_entry, dict(_IN_PROGRESS_ROUTING)]}
        )
        tracker.complete_stage("u1", "up1", UploadStage.ROUTING, "raw", "raw/k")
        vals = table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert vals[":entry"]["status"] == StageStatus.SUCCESS.value

    def test_find_stage_index_raises_when_list_empty(self):
        tracker, _ = _make_tracker()
        with pytest.raises(ValueError, match="No in-progress entry found for stage 'routing'"):
            tracker._find_stage_index([], UploadStage.ROUTING)

    def test_find_stage_index_raises_when_stage_already_completed(self):
        tracker, _ = _make_tracker()
        completed = [{"stage_name": "routing", "status": StageStatus.SUCCESS.value}]
        with pytest.raises(ValueError, match="No in-progress entry found"):
            tracker._find_stage_index(completed, UploadStage.ROUTING)

    def test_complete_stage_handles_missing_start_time(self):
        """processing_time should be None when start_time is absent."""
        bad_entry = {**_IN_PROGRESS_ROUTING}
        del bad_entry["start_time"]
        tracker, table = _make_tracker({"stage_progress": [bad_entry]})
        tracker.complete_stage("u1", "up1", UploadStage.ROUTING, "raw", "raw/k")
        vals = table.update_item.call_args[1]["ExpressionAttributeValues"]
        assert vals[":entry"]["processing_time"] is None
