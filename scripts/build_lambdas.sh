#!/usr/bin/env bash
# Build Lambda deployment ZIPs for all pipeline Lambdas.
#
# Each ZIP contains:
#   - lambda_function.py  (the Lambda handler)
#   - common/             (shared tracker + utilities)
#
# Output: lambda-packages/<name>.zip
#
# Usage:
#   ./scripts/build_lambdas.sh            # build all
#   ./scripts/build_lambdas.sh raw-to-processed-copy vector-generator

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/application/backend"
OUTPUT_DIR="$REPO_ROOT/lambda-packages"

mkdir -p "$OUTPUT_DIR"

build_lambda() {
    local name="$1"
    local src="$BACKEND_DIR/$name"
    local out="$OUTPUT_DIR/$name.zip"
    local tmp

    if [[ ! -d "$src" ]]; then
        echo "ERROR: Lambda source directory not found: $src" >&2
        return 1
    fi

    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' RETURN

    # Copy Lambda handler
    cp "$src/lambda_function.py" "$tmp/"

    # Copy shared common package
    cp -r "$BACKEND_DIR/common" "$tmp/common"

    # Remove __pycache__ and .pyc files
    find "$tmp" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$tmp" -name "*.pyc" -delete 2>/dev/null || true

    # Build ZIP (deterministic: sorted, no timestamps)
    (cd "$tmp" && zip -qr "$out" .)

    echo "Built $out"
}

# Default: build all known pipeline Lambdas
TARGETS=("${@:-raw-to-processed-copy vector-generator}")

if [[ $# -eq 0 ]]; then
    build_lambda "raw-to-processed-copy"
    build_lambda "vector-generator"
else
    for target in "$@"; do
        build_lambda "$target"
    done
fi
