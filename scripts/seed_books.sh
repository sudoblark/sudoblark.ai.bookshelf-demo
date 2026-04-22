#!/usr/bin/env bash
# Seed the bookshelf from a CSV catalogue file and kick off the enrichment pipeline.
#
# Reads book data from a pipe-separated CSV (default: scripts/seed_books.csv).
# Lines starting with # or blank lines are skipped.
# Expected format per line: title|author|published_year|isbn|description
#
# For each book:
#   1. Generates a UUID upload_id
#   2. Records USER_UPLOAD and ANALYSED tracking stages in DynamoDB
#   3. Writes metadata JSON to the raw S3 bucket (Hive-partitioned key)
#   4. Starts an enrichment state machine execution
#
# Usage:
#   ./scripts/seed_books.sh                                    # dry-run from default CSV
#   ./scripts/seed_books.sh --execute                          # seed from default CSV
#   ./scripts/seed_books.sh --execute --csv my.csv             # seed from custom CSV
#   ./scripts/seed_books.sh --execute --realistic-timestamps   # seed with realistic historical timestamps
#
# With --realistic-timestamps:
#   - Starting point: 2 days ago
#   - Each book's USER_UPLOAD: takes 1-5 seconds
#   - Each book's ANALYSED: takes 5-90 seconds
#   - Gap between books: 5-30 minutes (cumulative from previous book's end)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACCOUNT="aws-sudoblark-development"
PROJECT="bookshelf"
APPLICATION="demo"

RAW_BUCKET="${ACCOUNT}-${PROJECT}-${APPLICATION}-raw"
TRACKING_TABLE="${ACCOUNT}-${PROJECT}-${APPLICATION}-ingestion-tracking"

DRY_RUN=true
CSV_FILE="${SCRIPT_DIR}/seed_books.csv"
REALISTIC_TIMESTAMPS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --execute) DRY_RUN=false; shift ;;
        --csv) CSV_FILE="$2"; shift 2 ;;
        --realistic-timestamps) REALISTIC_TIMESTAMPS=true; shift ;;
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

# Generate random integer between min and max (inclusive)
random_int() {
    local min=$1
    local max=$2
    echo $((RANDOM % (max - min + 1) + min))
}

# Convert seconds since epoch to ISO 8601 timestamp
epoch_to_iso() {
    local epoch=$1
    if [[ "$OSTYPE" == "darwin"* ]]; then
        date -u -r "$epoch" +"%Y-%m-%dT%H:%M:%S+00:00"
    else
        date -u -d "@$epoch" +"%Y-%m-%dT%H:%M:%S+00:00"
    fi
}

# Initialize realistic timestamps: 2 days ago
now_epoch=$(date +%s)
start_epoch=$((now_epoch - 2 * 86400))  # 2 days ago in seconds
current_epoch=$start_epoch

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

    # Generate timestamps (realistic or current)
    if [[ "$REALISTIC_TIMESTAMPS" == "true" ]]; then
        # Add random gap between books (5-30 minutes)
        gap_seconds=$(random_int 300 1800)
        current_epoch=$((current_epoch + gap_seconds))

        # USER_UPLOAD stage: 1-5 seconds
        user_upload_start=$current_epoch
        user_upload_duration=$(random_int 1 5)
        user_upload_end=$((user_upload_start + user_upload_duration))

        # ANALYSED stage: 5-90 seconds, starts right after USER_UPLOAD
        analysed_start=$user_upload_end
        analysed_duration=$(random_int 5 90)
        analysed_end=$((analysed_start + analysed_duration))

        # Update current_epoch for next iteration
        current_epoch=$analysed_end

        user_upload_start_ts=$(epoch_to_iso "$user_upload_start")
        user_upload_end_ts=$(epoch_to_iso "$user_upload_end")
        analysed_start_ts=$(epoch_to_iso "$analysed_start")
        analysed_end_ts=$(epoch_to_iso "$analysed_end")
        created_at=$user_upload_start_ts
        updated_at=$analysed_end_ts
    else
        now=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
        user_upload_start_ts=$now
        user_upload_end_ts=$now
        analysed_start_ts=$now
        analysed_end_ts=$now
        created_at=$now
        updated_at=$now
    fi

    aws dynamodb put-item \
        --table-name "$TRACKING_TABLE" \
        --item "$(jq -n \
            --arg id "$upload_id" \
            --arg user_id "seeded" \
            --arg bucket "$RAW_BUCKET" \
            --arg key "$key" \
            --arg created_at "$created_at" \
            --arg updated_at "$updated_at" \
            --arg user_upload_start "$user_upload_start_ts" \
            --arg user_upload_end "$user_upload_end_ts" \
            --arg analysed_start "$analysed_start_ts" \
            --arg analysed_end "$analysed_end_ts" \
            '{
                upload_id: {S: $id},
                user_id: {S: $user_id},
                stage: {S: "analysed"},
                created_at: {S: $created_at},
                updated_at: {S: $updated_at},
                stages: {M: {
                    user_upload: {M: {
                        startedAt:         {S: $user_upload_start},
                        endedAt:           {S: $user_upload_end},
                        sourceBucket:      {S: $bucket},
                        sourceKey:         {S: $key},
                        destinationBucket: {S: $bucket},
                        destinationKey:    {S: $key}
                    }},
                    analysed: {M: {
                        startedAt:         {S: $analysed_start},
                        endedAt:           {S: $analysed_end},
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
