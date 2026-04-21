"""Tests for the ops handler (GET /ops/files and GET /ops/files/{file_id})."""

import importlib
import json
import os
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from fastapi import Request
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
    sys.modules.pop("ops_handler", None)
    sys.path.insert(
        0,
        os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
    )
    mod = importlib.import_module("ops_handler")
    return mod.OpsHandler(dynamodb_resource=dynamodb_resource)


def _seed(
    dynamodb_resource,
    upload_id,
    user_id=USER_ID,
    stage="analysed",
):
    table = dynamodb_resource.Table(TABLE_NAME)
    table.put_item(
        Item={
            "upload_id": upload_id,
            "user_id": user_id,
            "stage": stage,
            "stages": {
                "analysed": {
                    "startedAt": "2026-03-31T10:00:00+00:00",
                    "endedAt": "2026-03-31T10:00:02+00:00",
                    "sourceBucket": "landing",
                    "sourceKey": f"uploads/{user_id}/{upload_id}/cover.jpg",
                    "destinationBucket": "raw",
                    "destinationKey": f"uploads/{user_id}/{upload_id}/cover.jpg",
                },
            },
            "created_at": "2026-03-31T10:00:00+00:00",
            "updated_at": "2026-03-31T10:00:02+00:00",
        }
    )


def _mock_request() -> Request:
    """Create a mock FastAPI Request for testing."""
    return MagicMock(spec=Request)


# ---------------------------------------------------------------------------
# TestListFiles
# ---------------------------------------------------------------------------


class TestListFiles:
    @pytest.mark.asyncio
    async def test_returns_200_empty_list_when_table_is_empty(self, ops_handler):
        resp = await ops_handler.handle_list(_mock_request())
        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["files"] == []
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_returns_all_records(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        _seed(dynamodb_resource, UPLOAD_ID_B)
        resp = await ops_handler.handle_list(_mock_request())
        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["count"] == 2
        upload_ids = {r["upload_id"] for r in body["files"]}
        assert upload_ids == {UPLOAD_ID_A, UPLOAD_ID_B}

    @pytest.mark.asyncio
    async def test_each_record_has_required_fields(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_list(_mock_request())
        record = json.loads(resp.body.decode())["files"][0]
        assert "upload_id" in record
        assert "stage" in record
        assert "created_at" in record

    @pytest.mark.asyncio
    async def test_cors_header_present(self, ops_handler):
        resp = await ops_handler.handle_list(_mock_request())
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# TestGetFileById
# ---------------------------------------------------------------------------


class TestGetFileById:
    @pytest.mark.asyncio
    async def test_returns_200_with_full_record(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_get(_mock_request(), UPLOAD_ID_A)
        assert resp.status_code == 200
        body = json.loads(resp.body.decode())
        assert body["file"]["upload_id"] == UPLOAD_ID_A
        assert body["file"]["stage"] == "analysed"

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self, ops_handler):
        resp = await ops_handler.handle_get(_mock_request(), "nonexistent-id")
        assert resp.status_code == 404
        body = json.loads(resp.body.decode())
        assert "error" in body

    @pytest.mark.asyncio
    async def test_stages_included(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_get(_mock_request(), UPLOAD_ID_A)
        stages = json.loads(resp.body.decode())["file"]["stages"]
        assert "analysed" in stages

    @pytest.mark.asyncio
    async def test_cors_header_present(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_get(_mock_request(), UPLOAD_ID_A)
        assert resp.headers["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# TestStagesSerialisation
# ---------------------------------------------------------------------------


class TestStagesSerialisation:
    @pytest.mark.asyncio
    async def test_stages_dict_serialises_in_list(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_list(_mock_request())
        body = json.loads(resp.body.decode())
        record = body["files"][0]
        assert isinstance(record["stages"], dict)
        assert "analysed" in record["stages"]

    @pytest.mark.asyncio
    async def test_stages_dict_serialises_in_detail(self, ops_handler, dynamodb_resource):
        _seed(dynamodb_resource, UPLOAD_ID_A)
        resp = await ops_handler.handle_get(_mock_request(), UPLOAD_ID_A)
        body = json.loads(resp.body.decode())
        stages = body["file"]["stages"]
        assert isinstance(stages, dict)
        assert stages["analysed"]["destinationBucket"] == "raw"
