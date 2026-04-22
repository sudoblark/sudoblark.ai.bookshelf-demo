# ADR-0005: Upload Pipeline Stages

## Status

Accepted — supersedes ADR-0002

## Context

The bookshelf demo processes uploaded book cover images through a multi-stage
pipeline. Each stage is tracked in DynamoDB and the tracking table is the
single source of truth for pipeline state. This ADR documents the defined
stages, their semantics, the components responsible for each, and the data
schema used to record them.

## Pipeline Overview

```
User browser
    │
    │  1. Pre-signed PUT URL (landing bucket)
    ▼
Landing S3 bucket  ← USER_UPLOAD stage ends (file physically exists)
    │
    │  2. Streaming agent: Bedrock Claude extracts + user refines metadata
    │     POST /api/metadata/accept writes JSON → raw bucket
    ▼
Raw S3 bucket  ← ANALYSED stage ends (metadata extracted, refined, accepted)
    │
    │  3. Enrichment state machine fires (Step Functions)
    ▼
 ┌──────────────────────────────┐
 │  Enrichment State Machine    │
 │                              │
 │  raw-to-processed-copy       │  copies metadata JSON raw → processed
 │          │                   │  ← PROCESSED stage ends
 │          ▼                   │
 │  vector-generator            │  generates Bedrock Titan embedding,
 │                              │  writes .embedding.json → processed
 │                              │  ← EMBEDDING stage ends
 └──────────────────────────────┘
    │
    ▼
Processed S3 bucket
  author={author}/published_year={year}/{upload_id}.json
  author={author}/published_year={year}/{upload_id}.embedding.json
```

## Stages

Each stage is recorded in the `stages` dict on the DynamoDB tracking record.
The top-level `stage` field is set to the name of the last successfully
completed stage, or `"failed"` when any stage fails.

| Stage | Responsible component | Started by | Ended by | Meaning |
|---|---|---|---|---|
| `user_upload` | Presigned URL handler + browser | presigned URL generation | File lands in S3 | File physically exists and is accessible |
| `analysed` | Streaming agent (metadata handler → accept handler) | User begins extraction conversation | User saves book (accept) | Metadata extracted, refined by user, and formally accepted |
| `processed` | `raw-to-processed-copy` Lambda | Enrichment state machine | raw-to-processed-copy completes | Canonical metadata JSON copied to processed tier |
| `embedding` | `vector-generator` Lambda | Enrichment state machine (after processed) | vector-generator completes | Bedrock Titan embedding generated and stored |

### DynamoDB Schema

Each tracking record has this structure:

```json
{
  "upload_id": "abc-123-def-456",
  "user_id": "anonymous",
  "stage": "embedding",
  "created_at": "2026-04-20T10:00:00+00:00",
  "updated_at": "2026-04-20T10:00:15+00:00",
  "stages": {
    "user_upload": {
      "startedAt": "2026-04-20T10:00:00+00:00",
      "endedAt":   "2026-04-20T10:00:01+00:00",
      "sourceBucket":      "aws-sudoblark-development-bookshelf-demo-landing",
      "sourceKey":         "ui/uploads/abc-123-def-456/cover.jpg",
      "destinationBucket": "aws-sudoblark-development-bookshelf-demo-landing",
      "destinationKey":    "ui/uploads/abc-123-def-456/cover.jpg"
    },
    "analysed": {
      "startedAt": "2026-04-20T10:00:02+00:00",
      "endedAt":   "2026-04-20T10:00:10+00:00",
      "sourceBucket":      "aws-sudoblark-development-bookshelf-demo-landing",
      "sourceKey":         "ui/uploads/abc-123-def-456/cover.jpg",
      "destinationBucket": "aws-sudoblark-development-bookshelf-demo-raw",
      "destinationKey":    "author=Brandon_Sanderson/published_year=2010/abc-123-def-456.json"
    },
    "processed": {
      "startedAt": "2026-04-20T10:00:11+00:00",
      "endedAt":   "2026-04-20T10:00:12+00:00",
      "sourceBucket":      "aws-sudoblark-development-bookshelf-demo-raw",
      "sourceKey":         "author=Brandon_Sanderson/published_year=2010/abc-123-def-456.json",
      "destinationBucket": "aws-sudoblark-development-bookshelf-demo-processed",
      "destinationKey":    "author=Brandon_Sanderson/published_year=2010/abc-123-def-456.json"
    },
    "embedding": {
      "startedAt": "2026-04-20T10:00:13+00:00",
      "endedAt":   "2026-04-20T10:00:15+00:00",
      "sourceBucket":      "aws-sudoblark-development-bookshelf-demo-processed",
      "sourceKey":         "author=Brandon_Sanderson/published_year=2010/abc-123-def-456.json",
      "destinationBucket": "aws-sudoblark-development-bookshelf-demo-processed",
      "destinationKey":    "author=Brandon_Sanderson/published_year=2010/abc-123-def-456.embedding.json"
    }
  }
}
```

### Top-level `stage` field

The `stage` field is always set to:
- The name of the last successfully completed stage (e.g., `"embedding"`, `"processed"`, `"analysed"`)
- Or `"failed"` if any stage failed

Failed stages include an `"error"` field in their `stages[stage_name]` entry with a human-readable reason.

## Detailed Flow

### USER_UPLOAD Stage

**Started:** When presigned URL handler generates a signed URL and returns `session_id`.

**Ended:** When file successfully lands in S3 landing bucket (user uploads via browser).

**Responsible component:** Metadata handler (on first extraction call).

**Semantics:** "Does the file physically exist in S3?" Timing: seconds.

### ANALYSED Stage

**Started:** When user begins metadata extraction (POST `/api/metadata/extract` with bucket and key).

**Ended:** When user saves the book (POST `/api/metadata/accept` completes successfully).

**Responsible component:** Metadata handler (start) → Accept handler (end).

**Semantics:** "Has the user extracted, refined, and formally accepted metadata?" Timing: minutes (user may pause between extraction and acceptance).

### PROCESSED Stage

**Started:** Enrichment state machine invokes `raw-to-processed-copy` Lambda.

**Ended:** `raw-to-processed-copy` Lambda completes successfully.

**Responsible component:** `raw-to-processed-copy` Lambda.

**Semantics:** "Is canonical metadata copied to the processed tier?" Timing: seconds.

### EMBEDDING Stage

**Started:** Enrichment state machine invokes `vector-generator` Lambda (after PROCESSED completes).

**Ended:** `vector-generator` Lambda completes successfully.

**Responsible component:** `vector-generator` Lambda.

**Semantics:** "Has a semantic embedding been generated for similarity search?" Timing: seconds.

## Read Path

The bookshelf handler (catalogue, search, related, graph endpoints) reads
exclusively from DynamoDB rather than scanning S3. This avoids full bucket
scans and ensures only accepted books are surfaced.

- **Catalogue / search**: records with a completed `analysed` stage
  (i.e. `stage` is `analysed`, `processed`, or `embedding`).
- **Embeddings for similarity**: records with a completed `embedding` stage;
  the embedding S3 key is derived from the `embedding` stage's
  `destinationBucket` / `destinationKey`.

## Components

### Metadata handler (`metadata_handler`)

**On first call (bucket + key provided):**
- Creates tracking record
- Marks `user_upload` stage complete (file already in S3)
- Starts `analysed` stage

**On extraction/refinement calls:**
- Loads message history for multi-turn conversation
- Agent calls metadata extraction tools
- Does NOT mark stages complete

### Accept handler (`accept_handler`)

- Writes metadata JSON to raw bucket
- Marks `analysed` stage complete
- Fires the enrichment Step Functions state machine as a fire-and-forget call
  (accept succeeds even if state machine trigger fails)

### Enrichment state machine

A Step Functions state machine whose sole input is `{"upload_id": "..."}`.
Its current definition is a two-state sequence:

1. **CopyToProcessed** — invokes `raw-to-processed-copy`
2. **GenerateEmbedding** — invokes `vector-generator`

Both states carry a retry policy for transient Lambda / Bedrock errors.

### `raw-to-processed-copy` Lambda

Reads the metadata JSON from the raw bucket (key from the `analysed` stage
entry in DynamoDB), writes it to the processed bucket at the same key path,
and marks the `processed` stage complete.

### `vector-generator` Lambda

Reads the metadata JSON from the processed bucket (key from the `processed`
stage entry in DynamoDB), calls Bedrock Titan (`amazon.titan-embed-text-v1`)
with the book description (falls back to `"{title} by {author}"`), writes
`{upload_id}.embedding.json` to the same processed prefix, and marks the
`embedding` stage complete.

## Key naming convention

All objects in raw and processed use Hive-style partitioning:

```
author={sanitised_author}/published_year={year}/{upload_id}.json
author={sanitised_author}/published_year={year}/{upload_id}.embedding.json
```

`{sanitised_author}` has non-alphanumeric characters replaced with `_`.

## Consequences

**✅ Single source of truth** — DynamoDB is authoritative; no S3 bucket scans
required for the read path.

**✅ Observable** — Every stage transition (start, complete, fail) is recorded
with timestamps and source/destination keys. The ops dashboard reflects
pipeline state in real time.

**✅ Clear user-visible states** — USER_UPLOAD shows file upload progress;
ANALYSED shows extraction/refinement progress; PROCESSED and EMBEDDING show
backend processing.

**⚠️ Async abandonment** — If a user accepts metadata but navigates away before
embedding completes, the `analysed` stage is complete and the book appears in
the catalogue, but `stage` will remain `analysed` until the state machine
finishes. This is intentional.

**⚠️ Stage naming is canonical** — Renaming stages requires a data migration
(see `scripts/migrate_tracking_schema.py` for the migration pattern).
