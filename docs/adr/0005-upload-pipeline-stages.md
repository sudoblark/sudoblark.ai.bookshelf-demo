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
Landing S3 bucket
    │
    │  2. Streaming agent: Bedrock Claude extracts + user refines metadata
    │     POST /api/metadata/accept writes JSON → raw bucket
    ▼
Raw S3 bucket
    │
    │  3. Enrichment state machine fires (Step Functions)
    ▼
 ┌──────────────────────────────┐
 │  Enrichment State Machine    │
 │                              │
 │  raw-to-processed-copy       │  copies metadata JSON raw → processed
 │          │                   │
 │          ▼                   │
 │  vector-generator            │  generates Bedrock Titan embedding,
 │                              │  writes .embedding.json → processed
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

| Stage | Responsible component | Source | Destination | Meaning |
|---|---|---|---|---|
| `queued` | Streaming agent (presigned handler) | — | landing | File physically exists in S3 |
| `analysed` | Streaming agent (accept handler) | landing | raw | Metadata extracted, refined, and accepted by user |
| `processed` | `raw-to-processed-copy` Lambda | raw | processed | Canonical metadata JSON in the processed tier |
| `embedding` | `vector-generator` Lambda | processed | processed | Bedrock Titan embedding stored alongside metadata |

### Stage schema

Each entry in the `stages` dict:

```json
{
  "startedAt": "2026-04-20T10:00:00+00:00",
  "endedAt":   "2026-04-20T10:00:03+00:00",
  "sourceBucket":      "aws-sudoblark-development-bookshelf-demo-landing",
  "sourceKey":         "ui/uploads/{upload_id}/cover.jpg",
  "destinationBucket": "aws-sudoblark-development-bookshelf-demo-raw",
  "destinationKey":    "author=Brandon_Sanderson/published_year=2010/{upload_id}.json"
}
```

Failed stages additionally carry an `"error"` field with a human-readable
reason.

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

### Streaming agent (`accept_handler`)

Writes the metadata JSON to the raw bucket and marks the `analysed` stage
complete. Fires the enrichment Step Functions state machine as a
fire-and-forget call — accept succeeds even if the state machine trigger
fails.

### Enrichment state machine

A Step Functions state machine whose sole input is `{"upload_id": "..."}`.
Its current definition is a two-state sequence:

1. **CopyToProcessed** — invokes `raw-to-processed-copy`
2. **GenerateEmbedding** — invokes `vector-generator`

Both states carry a retry policy for transient Lambda / Bedrock errors. The
state machine is intentionally generic: additional enrichment steps (e.g.
classification, tagging) can be inserted without changing the upstream
pipeline.

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

**✅ Extensible** — New enrichment steps are added to the state machine without
touching the upstream streaming agent.

**⚠️ Async abandonment** — If a user accepts metadata but navigates away before
embedding completes, the `analysed` stage is complete and the book appears in
the catalogue, but `stage` will remain `analysed` until the state machine
finishes. This is intentional.

**⚠️ Stage naming is canonical** — Renaming stages requires a data migration
(see `scripts/migrate_tracking_schema.py` for the migration pattern).
