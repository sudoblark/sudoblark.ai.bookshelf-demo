#!/usr/bin/env bash
# Seed the bookshelf from a CSV catalogue file and kick off the enrichment pipeline.
#
# Reads book data from a pipe-separated CSV (default: scripts/seed_books.csv).
# Lines starting with # or blank lines are skipped.
# Expected format per line: title|author|published_year|isbn|description
#
# For each book:
#   1. Generates a UUID upload_id
#   2. Writes metadata JSON to the raw S3 bucket (Hive-partitioned key)
#   3. Records an ANALYSED tracking entry in DynamoDB
#   4. Starts an enrichment state machine execution
#
# Usage:
#   ./scripts/seed_books.sh                          # dry-run from default CSV
#   ./scripts/seed_books.sh --execute                # seed from default CSV
#   ./scripts/seed_books.sh --execute --csv my.csv   # seed from custom CSV

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACCOUNT="aws-sudoblark-development"
PROJECT="bookshelf"
APPLICATION="demo"

RAW_BUCKET="${ACCOUNT}-${PROJECT}-${APPLICATION}-raw"
TRACKING_TABLE="${ACCOUNT}-${PROJECT}-${APPLICATION}-ingestion-tracking"

DRY_RUN=true
CSV_FILE="${SCRIPT_DIR}/seed_books.csv"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --execute) DRY_RUN=false; shift ;;
        --csv) CSV_FILE="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ ! -f "$CSV_FILE" ]]; then
    echo "ERROR: CSV file not found: $CSV_FILE" >&2
    exit 1
fi

if [[ "$DRY_RUN" == "false" ]]; then
    STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
        --query "stateMachines[?name=='${ACCOUNT}-${PROJECT}-${APPLICATION}-enrichment'].stateMachineArn" \
        --output text)
    if [[ -z "$STATE_MACHINE_ARN" ]]; then
        echo "ERROR: Could not find enrichment state machine. Is the infrastructure deployed?" >&2
        exit 1
    fi
else
    STATE_MACHINE_ARN="(not resolved — dry-run)"
fi

echo "CSV file:       $CSV_FILE"
echo "Raw bucket:     $RAW_BUCKET"
echo "Tracking table: $TRACKING_TABLE"
echo "State machine:  $STATE_MACHINE_ARN"
echo ""

sanitise() {
    echo "$1" | sed 's/[^a-zA-Z0-9 _.,-]/_/g' | xargs
}

COUNT=0
while IFS= read -r line; do
    # Skip comments and blank lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line//[[:space:]]/}" ]] && continue

    IFS='|' read -r title author year isbn description <<< "$line"

    upload_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    author_sanitised=$(sanitise "$author")
    key="author=${author_sanitised}/published_year=${year}/${upload_id}.json"

    COUNT=$((COUNT + 1))

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "[dry-run] $title ($author, $year) → s3://$RAW_BUCKET/$key"
        continue
    fi

    metadata=$(jq -n \
        --arg upload_id "$upload_id" \
        --arg title "$title" \
        --arg author "$author" \
        --arg year "$year" \
        --arg isbn "$isbn" \
        --arg description "$description" \
        '{
            upload_id: $upload_id,
            title: $title,
            author: $author,
            published_year: ($year | tonumber),
            isbn: $isbn,
            description: $description,
            filename: "manual-seed"
        }')

    echo "$metadata" | aws s3 cp - "s3://$RAW_BUCKET/$key" \
        --content-type "application/json" \
        --no-progress

    now=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
    aws dynamodb put-item \
        --table-name "$TRACKING_TABLE" \
        --item "$(jq -n \
            --arg id "$upload_id" \
            --arg bucket "$RAW_BUCKET" \
            --arg key "$key" \
            --arg now "$now" \
            '{
                upload_id: {S: $id},
                stage: {S: "analysed"},
                stages: {M: {
                    analysed: {M: {
                        startedAt:         {S: $now},
                        endedAt:           {S: $now},
                        sourceBucket:      {S: $bucket},
                        sourceKey:         {S: $key},
                        destinationBucket: {S: $bucket},
                        destinationKey:    {S: $key}
                    }}
                }}
            }')"

    exec_arn=$(aws stepfunctions start-execution \
        --state-machine-arn "$STATE_MACHINE_ARN" \
        --input "{\"upload_id\": \"$upload_id\"}" \
        --query "executionArn" \
        --output text)

    echo "Seeded: $title → $exec_arn"

done < "$CSV_FILE"

echo ""
if [[ "$DRY_RUN" == "true" ]]; then
    echo "$COUNT book(s) would be seeded. Pass --execute to run."
else
    echo "$COUNT book(s) seeded and enrichment triggered."
fi
