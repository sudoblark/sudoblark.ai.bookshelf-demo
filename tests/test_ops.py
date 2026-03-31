"""Tests for the ops Lambda handler (GET /ops/files and GET /ops/files/{file_id})."""

import importlib
import json
import sys
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "test-ingestion-tracking"
USER_ID = "user-123"
UPLOAD_ID_A = "upload-aaa"
UPLOAD_ID_B = "upload-bbb"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dynamodb_resource(aws_credentials):
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-west-2")
        resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "upload_id", "KeyType": "HASH"}],
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
def ops_handler(dynamodb_resource, monkeypatch):
    monkeypatch.setenv("TRACKING_TABLE", TABLE_NAME)
    # Force reimport so the module-level singleton picks up the test table name.
    sys.modules.pop("lambda_function", None)
    sys.path.insert(
        0,
        __import__("os").path.join(
            __import__("os").path.dirname(__file__), "../application/backend/restapi/ops"
        ),
    )
    mod = importlib.import_module("lambda_function")
    return mod.OpsHandler(dynamodb_resource=dynamodb_resource)


def _seed(
    dynamodb_resource, upload_id, user_id=USER_ID, status="SUCCESS", stage_processing_time=None
):
    table = dynamodb_resource.Table(TABLE_NAME)
    stage_entry = {
        "stage_name": "av_scan",
        "status": "success",
        "start_time": "2026-03-31T10:00:00+00:00",
        "end_time": "2026-03-31T10:00:02+00:00",
        "processing_time": stage_processing_time or Decimal("2.345"),
        "source": {"bucket": "landing", "key": f"uploads/{user_id}/{upload_id}/cover.jpg"},
        "destination": {"bucket": "raw", "key": f"uploads/{user_id}/{upload_id}/cover.jpg"},
        "error_message": None,
    }
    table.put_item(
        Item={
            "upload_id": upload_id,
            "user_id": user_id,
            "current_status": status,
            "stage_progress": [stage_entry],
            "created_at": "2026-03-31T10:00:00+00:00",
            "updated_at": "2026-03-31T10:00:02+00:00",
        }
    )


def _list_event():
    return {"pathParameters": None}


def _detail_event(file_id):
    return {"pathParameters": {"file_id": file_id}}


# ---------------------------------------------------------------------------
# TestListFiles
# ---------------------------------------------------------------------------


class TestListFiles:
    def test_returns_200_empty_list_when_table_is_empty(self, ops_handler):
        resp = ops_handler(_list_event())
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["files"] == []
        assert body["count"] == 0

    def test_returns_all_records(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        _seed(dynamodb_resource, UPLOAD_ID_B)
        resp = ops_handler(_list_event())
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["count"] == 2
        upload_ids = {r["upload_id"] for r in body["files"]}
        assert upload_ids == {UPLOAD_ID_A, UPLOAD_ID_B}

    def test_each_record_has_required_fields(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = ops_handler(_list_event())
        record = json.loads(resp["body"])["files"][0]
        assert "upload_id" in record
        assert "current_status" in record
        assert "created_at" in record

    def test_cors_header_present(self, ops_handler):
        resp = ops_handler(_list_event())
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# TestGetFileById
# ---------------------------------------------------------------------------


class TestGetFileById:
    def test_returns_200_with_full_record(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = ops_handler(_detail_event(UPLOAD_ID_A))
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["file"]["upload_id"] == UPLOAD_ID_A
        assert body["file"]["current_status"] == "SUCCESS"

    def test_returns_404_when_not_found(self, ops_handler):
        resp = ops_handler(_detail_event("nonexistent-id"))
        assert resp["statusCode"] == 404
        body = json.loads(resp["body"])
        assert "error" in body

    def test_stage_progress_included(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = ops_handler(_detail_event(UPLOAD_ID_A))
        stages = json.loads(resp["body"])["file"]["stage_progress"]
        assert len(stages) == 1
        assert stages[0]["stage_name"] == "av_scan"

    def test_cors_header_present(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = ops_handler(_detail_event(UPLOAD_ID_A))
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# TestDecimalSerialisation
# ---------------------------------------------------------------------------


class TestDecimalSerialisation:
    def test_processing_time_decimal_serialises_in_list(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A, stage_processing_time=Decimal("2.345"))
        resp = ops_handler(_list_event())
        # Must not raise — body should be valid JSON with processing_time as a string
        body = json.loads(resp["body"])
        stage = body["files"][0]["stage_progress"][0]
        assert stage["processing_time"] == "2.345"

    def test_processing_time_decimal_serialises_in_detail(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A, stage_processing_time=Decimal("1.001"))
        resp = ops_handler(_detail_event(UPLOAD_ID_A))
        body = json.loads(resp["body"])
        stage = body["file"]["stage_progress"][0]
        assert stage["processing_time"] == "1.001"
