"""Tests for lambda-packages/common shared utilities."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from common.handler import BaseS3BatchHandler
from common.response import build_response
from common.s3 import resolve_bucket, validate_key

# ---------------------------------------------------------------------------
# Minimal concrete implementation used to test BaseS3BatchHandler directly
# ---------------------------------------------------------------------------


class _IdentityHandler(BaseS3BatchHandler):
    """Returns the key unchanged; records each processed key for assertions."""

    def __init__(self, s3_client: Any = None) -> None:
        super().__init__(s3_client)
        self.processed: list = []

    def process_record(self, bucket: str, key: str) -> str:
        self.processed.append(key)
        return key


class _RaisingHandler(BaseS3BatchHandler):
    """Always raises from process_record to exercise failure paths."""

    def process_record(self, bucket: str, key: str) -> str:
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


class TestBaseS3BatchHandler:
    def test_logger_named_after_concrete_class(self):
        h = _IdentityHandler(s3_client=MagicMock())
        assert h.logger.name == "_IdentityHandler"

    def test_processes_record_and_returns_200(self):
        h = _IdentityHandler(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/u/up/cover.jpg"), None)
        assert result["statusCode"] == 200
        assert result["processed_count"] == 1
        assert "uploads/u/up/cover.jpg" in result["processed_files"]

    def test_records_failure_and_returns_207(self):
        h = _RaisingHandler(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/u/up/cover.jpg"), None)
        assert result["statusCode"] == 207
        assert result["failed_count"] == 1
        assert "processing failed" in result["failed_files"][0]["error"]

    def test_rejects_path_traversal_before_process_record(self):
        h = _IdentityHandler(s3_client=MagicMock())
        result = h(_make_s3_event("my-bucket", "uploads/../secret/file.jpg"), None)
        assert result["statusCode"] == 207
        assert len(h.processed) == 0  # process_record was never called


class TestResolveBucket:
    def test_resolves_landing_to_raw(self):
        result = resolve_bucket("aws-sudoblark-development-bookshelf-demo-landing", "raw")
        assert result == "aws-sudoblark-development-bookshelf-demo-raw"

    def test_resolves_raw_to_processed(self):
        result = resolve_bucket("aws-sudoblark-development-bookshelf-demo-raw", "processed")
        assert result == "aws-sudoblark-development-bookshelf-demo-processed"

    def test_raises_for_short_bucket_name(self):
        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            resolve_bucket("bad-name", "raw")

    def test_raises_for_three_segment_name(self):
        with pytest.raises(ValueError, match="Invalid source bucket name format"):
            resolve_bucket("account-project-landing", "raw")


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
