#!/bin/bash

#
# Bundle Lambda Functions with Dependencies
#
# This script packages all Lambda functions with their Python dependencies
# into ZIP files in the lambda-packages/ directory for Terraform deployment.
#
# Usage: ./scripts/bundle-lambdas.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Directories - source and output both live under lambda-packages/
LAMBDA_SOURCE_DIR="${PROJECT_ROOT}/lambda-packages"
OUTPUT_DIR="${PROJECT_ROOT}/lambda-packages"
TEMP_DIR="${OUTPUT_DIR}/tmp"

# Lambda functions to bundle
LAMBDAS=(
  "unzip-processor"   # TODO: rename to av-scanner once lambda code is refactored
  "metadata-extractor"
)

# Function to bundle a Lambda with dependencies
bundle_lambda() {
  local lambda_name=$1
  local source_dir="${LAMBDA_SOURCE_DIR}/${lambda_name}"
  local requirements_file="${source_dir}/requirements.txt"
  local output_file="${OUTPUT_DIR}/${lambda_name}.zip"
  local temp_build_dir="${TEMP_DIR}/${lambda_name}"

  if [ ! -d "$source_dir" ]; then
    echo -e "${RED}✗${NC} Source directory not found: ${source_dir}"
    return 1
  fi

  echo -e "${YELLOW}→${NC} Bundling ${lambda_name}..."

  # Create clean temp build directory
  rm -rf "$temp_build_dir"
  mkdir -p "$temp_build_dir"

  # Copy Lambda source code (exclude requirements files and README)
  cp -r "${source_dir}"/* "${temp_build_dir}/"
  rm -f "${temp_build_dir}/requirements.txt" \
        "${temp_build_dir}/requirements-ci.txt" \
        "${temp_build_dir}/README.md"

  # Install dependencies if requirements.txt exists
  if [ -f "$requirements_file" ]; then
    echo -e "${YELLOW}  →${NC} Installing dependencies from requirements.txt..."
    # --platform and --only-binary ensure Linux x86_64 wheels are downloaded
    # even when bundling from macOS, preventing ELF header errors at Lambda runtime.
    pip install -q \
      --target "$temp_build_dir" \
      --platform manylinux2014_x86_64 \
      --python-version 3.11 \
      --only-binary=:all: \
      --upgrade \
      -r "$requirements_file"
    echo -e "${GREEN}  ✓${NC} Dependencies installed (linux/x86_64)"
  else
    echo -e "${YELLOW}  →${NC} No requirements.txt found, skipping dependency installation"
  fi

  # Create ZIP file
  echo -e "${YELLOW}  →${NC} Creating ZIP archive..."
  pushd "$temp_build_dir" > /dev/null || return 1
  zip -r -q "$output_file" . || { popd > /dev/null; return 1; }
  popd > /dev/null || return 1

  # Get file size
  local size
  size=$(du -h "$output_file" | cut -f1)

  echo -e "${GREEN}✓${NC} Created ${lambda_name}.zip (${size})"

  return 0
}

# Main execution
echo "================================================="
echo "Lambda Function Bundler"
echo "================================================="
echo ""

# Check Python is available
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}✗${NC} Python 3 is not installed"
  exit 1
fi

if ! command -v pip &> /dev/null; then
  echo -e "${RED}✗${NC} pip is not installed"
  exit 1
fi

echo -e "${GREEN}✓${NC} Python $(python3 --version | cut -d' ' -f2) found"
echo -e "${GREEN}✓${NC} pip $(pip --version | cut -d' ' -f2) found"
echo ""

# Create temp directory and clean up any previous run
mkdir -p "$OUTPUT_DIR"
rm -rf "$TEMP_DIR"
echo -e "${GREEN}✓${NC} Output directory: ${OUTPUT_DIR}"
echo ""

# Bundle each Lambda
success_count=0
fail_count=0

for lambda in "${LAMBDAS[@]}"; do
  if bundle_lambda "$lambda"; then
    success_count=$((success_count + 1))
  else
    fail_count=$((fail_count + 1))
  fi
done

# Clean up temp directory
rm -rf "$TEMP_DIR"

# Summary
echo ""
echo "================================================="
echo "Summary"
echo "================================================="
echo -e "Success: ${GREEN}${success_count}${NC}"
echo -e "Failed:  ${RED}${fail_count}${NC}"
echo ""

if [ $fail_count -eq 0 ]; then
  echo -e "${GREEN}✓${NC} All Lambda functions bundled successfully!"
  exit 0
else
  echo -e "${RED}✗${NC} Some Lambda functions failed to bundle"
  exit 1
fi
