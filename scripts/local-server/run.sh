#!/usr/bin/env bash
# Run the bookshelf streaming-agent service locally via Docker.
#
# Exports the current AWS SSO session as static credentials and injects them
# into the container — avoids the SSO token refresh flow that cannot run
# inside Docker.
#
# Usage:
#   ./scripts/local-server/run.sh
#
# Environment variables (all optional — sensible defaults are set below):
#   AWS_PROFILE      AWS profile to export credentials from
#   LANDING_BUCKET   S3 landing bucket name
#   RAW_BUCKET       S3 raw bucket name
#   BEDROCK_MODEL_ID Bedrock model ID override
#   LOG_LEVEL        Python log level (default: INFO)

set -euo pipefail

PROFILE="${AWS_PROFILE:-sudoblark-development}"

echo "Exporting SSO credentials for profile: $PROFILE"
eval "$(aws configure export-credentials --profile "$PROFILE" --format env)"
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

echo "Exporting eu-west-2 as hard-coded region"
export AWS_DEFAULT_REGION=eu-west-2

echo "Exporting bucket names"
export LANDING_BUCKET="${LANDING_BUCKET:-aws-sudoblark-development-bookshelf-demo-landing}"
export RAW_BUCKET="${RAW_BUCKET:-aws-sudoblark-development-bookshelf-demo-raw}"

export BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-anthropic.claude-3-haiku-20240307-v1:0}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../application/backend/streaming-agent"

exec docker-compose up --build
