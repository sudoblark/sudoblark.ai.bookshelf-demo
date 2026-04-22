# ADR-0002: Upload Pipeline Stages

## Status
Superseded by ADR-0005

**This ADR describes an old tracking schema and has been replaced. See [ADR-0005](0005-upload-pipeline-stages.md) for the current implementation.**

## Context

The bookshelf demo pipeline processes uploaded book covers through multiple stages:
file upload → metadata extraction → optional refinement → acceptance and storage.

We need a consistent, trackable model for observing and monitoring the progress of each upload through this pipeline. The DynamoDB ingestion-tracking table stores a `stage_progress` list that records when each stage begins, completes, or fails, with associated timestamps and error messages.

This ADR documents the defined stages and their semantics.

## Decision

**Four pipeline stages are defined** for each upload, processed sequentially:

| Stage | Started | Completed | Semantics |
|-------|---------|-----------|-----------|
| **USER_UPLOAD** | File handed to presigned URL | Browser uploads to S3 landing bucket | "Does the file physically exist in S3?" Timing: ~seconds |
| **ENRICHMENT** | `/api/metadata/initial` called | `/api/metadata/accept` saves to raw bucket | "Has the user extracted, refined, and accepted metadata?" Timing: minutes (user may pause between steps) |
| **ROUTING** | (future) | (future) | Move file from landing → processing bucket (security, validation) |
| **AV_SCAN** | (future) | (future) | Antivirus scan on processed file |

## Rationale

**Why these four stages?**

1. **USER_UPLOAD**: Separates the browser's responsibility (upload success) from the backend's responsibilities (processing). If this fails, no further work can proceed.

2. **ENRICHMENT**: Groups the entire AI-driven extraction workflow (initial extraction + user refinement loop + final acceptance). Stays IN_PROGRESS while the user is deciding what to do; completes only when they explicitly accept. If Bedrock throttles, this stage fails immediately, and the ops dashboard shows it.

3. **ROUTING & AV_SCAN**: Placeholder for post-acceptance processing (moving files to secure storage, scanning, indexing). Not yet implemented but reserved to avoid schema churn later.

## Status Semantics

Each stage can be in one of three states:

- **IN_PROGRESS**: Started but not yet completed (or failed)
- **SUCCESS**: Completed without errors
- **FAILED**: Stopped due to an error (reason in `error_message` field)

### Example: Failed Extraction

Upload flow when Bedrock API returns 429:

```json
{
  "upload_id": "abc-123",
  "current_status": "FAILED",
  "stage_progress": [
    {
      "stage_name": "user_upload",
      "status": "success",
      "start_time": "2026-04-15T14:32:00Z",
      "end_time": "2026-04-15T14:32:05Z",
      "processing_time": 5.234,
      "source": {"bucket": "landing", "key": "ui/uploads/abc-123/cover.jpg"},
      "destination": {"bucket": "landing", "key": "ui/uploads/abc-123/cover.jpg"},
      "error_message": null
    },
    {
      "stage_name": "enrichment",
      "status": "failed",
      "start_time": "2026-04-15T14:32:06Z",
      "end_time": "2026-04-15T14:32:15Z",
      "processing_time": 9.156,
      "source": {"bucket": "landing", "key": "ui/uploads/abc-123/cover.jpg"},
      "destination": null,
      "error_message": "Bedrock API error: ModelHTTPError: status_code: 429"
    }
  ]
}
```

The ops dashboard then displays:
- Overall status: **FAILED** (red)
- USER_UPLOAD: ✓ success (green checkmark)
- ENRICHMENT: ✕ failed (red X) with error visible on expand

### Example: Successful Upload

```json
{
  "upload_id": "xyz-789",
  "current_status": "SUCCESS",
  "stage_progress": [
    {
      "stage_name": "user_upload",
      "status": "success",
      "processing_time": 3.542,
      ...
    },
    {
      "stage_name": "enrichment",
      "status": "success",
      "processing_time": 45.128,
      "destination": {"bucket": "raw", "key": "author=Brandon_Sanderson/published_year=2010/xyz-789.json"},
      ...
    }
  ]
}
```

### Example: Incomplete Upload (User navigated away without accepting)

```json
{
  "upload_id": "def-456",
  "current_status": "IN_PROGRESS",
  "stage_progress": [
    {
      "stage_name": "user_upload",
      "status": "success",
      "processing_time": 2.891,
      ...
    },
    {
      "stage_name": "enrichment",
      "status": "in_progress",
      "start_time": "2026-04-15T14:35:00Z",
      "end_time": null,
      "processing_time": null,
      "destination": null,
      "error_message": null
    }
  ]
}
```

Ops dashboard shows: **IN PROGRESS** (yellow), with ENRICHMENT still spinning.
This is correct — the user hasn't finished the workflow yet.

## Implementation Notes

**Frontend & Backend:**
- Frontend navigation away from MetadataPage clears the session but does **not** abort the backend stream or cancel tracking
- If user navigates away during extraction, ENRICHMENT stays IN_PROGRESS until they return or the extraction fails
- Each new "New book" session is independent (upload context is cleared on tab navigation)

**Tracking Calls:**
- `tracker.create_record()` → Initialize tracking, set status QUEUED
- `tracker.start_stage(stage)` → Append in-progress stage entry, set status IN_PROGRESS
- `tracker.complete_stage(stage)` → Update most-recent stage entry to SUCCESS, set status to SUCCESS (if all stages done)
- `tracker.fail_stage(stage, error_message)` → Update most-recent stage entry to FAILED, set status to FAILED

**Future Stages (ROUTING, AV_SCAN):**
When implemented, these will be started/completed by backend Lambda functions after ENRICHMENT completes. The DynamoDB schema already supports them; no changes needed.

## Consequences

✅ **Clear mental model**: Each stage has a well-defined start/end and semantic meaning.

✅ **Observable failures**: Failed extractions (429, timeouts, etc.) are immediately visible in ops dashboard.

✅ **User control**: User can abandon the enrichment workflow mid-way, and the tracking record correctly reflects "IN_PROGRESS".

⚠️ **Schema lock-in**: Adding new stages in the future requires no schema changes, but the stage names are now canonical. Renaming stages requires a migration.

⚠️ **Async abandonment**: User can navigate away and leave ENRICHMENT in IN_PROGRESS indefinitely. This is intentional but must be documented (ops dashboard will show orphaned uploads).
