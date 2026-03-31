#!/bin/bash

#
# Bundle Lambda Functions and Layers with Dependencies
#
# This script packages all Lambda functions and layers with their Python
# dependencies into ZIP files in the lambda-packages/ directory for
# Terraform deployment.
#
# Source code lives under application/backend/ following the logical boundaries
# that would be separate repos in a production micro-repo setup:
#   application/backend/common/            — shared utilities (PyPI package equivalent)
#   application/backend/data-pipeline/    — Step Functions pipeline Lambdas + agent layer
#   application/backend/restapi/          — REST API Lambdas
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

# Source roots
COMMON_DIR="${PROJECT_ROOT}/application/backend/common"
DATA_PIPELINE_DIR="${PROJECT_ROOT}/application/backend/data-pipeline"
RESTAPI_DIR="${PROJECT_ROOT}/application/backend/restapi"

# ZIP output stays in lambda-packages/ — referenced by Terraform
OUTPUT_DIR="${PROJECT_ROOT}/lambda-packages"
TEMP_DIR="${OUTPUT_DIR}/tmp"

# Returns space-separated glob patterns for packages to remove after pip install
# for a given Lambda. These packages are already provided by an attached Lambda
# layer and count against the 262 MB unzipped deployment limit.
# Uses a case statement for bash 3 compatibility (macOS ships bash 3.2).
layer_exclude_packages() {
  local name=$1
  case "$name" in
    bookshelf-agent)
      # Exclude packages provided by the Lambda runtime so they don't bloat the layer.
      # pydantic-ai-slim[bedrock] declares boto3 as a dep; botocore alone is ~75 MB unzipped.
      echo "boto3 boto3-*.dist-info botocore botocore-*.dist-info s3transfer s3transfer-*.dist-info jmespath jmespath-*.dist-info"
      ;;
    metadata-extractor)
      echo "boto3 boto3-*.dist-info botocore botocore-*.dist-info s3transfer s3transfer-*.dist-info jmespath jmespath-*.dist-info Pillow Pillow-*.dist-info pydantic pydantic-*.dist-info pydantic_ai pydantic_ai-*.dist-info pydantic_ai_slim pydantic_ai_slim-*.dist-info"
      ;;
    *)
      echo ""
      ;;
  esac
}

# Function to bundle a Lambda layer
# Lambda layers require a python/ directory at the ZIP root so that Lambda
# adds the contents to sys.path at /opt/python.
# Args: layer_name source_dir
bundle_layer() {
  local layer_name=$1
  local source_dir=$2
  local requirements_file="${source_dir}/requirements.txt"
  local output_file="${OUTPUT_DIR}/${layer_name}.zip"
  local temp_build_dir="${TEMP_DIR}/${layer_name}/python"

  if [ ! -d "$source_dir" ]; then
    echo -e "${RED}✗${NC} Source directory not found: ${source_dir}"
    return 1
  fi

  echo -e "${YELLOW}→${NC} Bundling layer ${layer_name}..."

  # Create clean temp build directory with python/ subdirectory
  rm -rf "${TEMP_DIR}/${layer_name}"
  mkdir -p "$temp_build_dir"

  # Copy layer source code (exclude requirements files and README)
  cp -r "${source_dir}"/* "${temp_build_dir}/"
  rm -f "${temp_build_dir}/requirements.txt" \
        "${temp_build_dir}/requirements-ci.txt" \
        "${temp_build_dir}/README.md"

  # Install dependencies if requirements.txt exists
  if [ -f "$requirements_file" ]; then
    echo -e "${YELLOW}  →${NC} Installing dependencies from requirements.txt..."
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

  # Remove packages already provided by the Lambda runtime
  local exclude_pkgs
  exclude_pkgs=$(layer_exclude_packages "$layer_name")
  if [ -n "$exclude_pkgs" ]; then
    echo -e "${YELLOW}  →${NC} Removing runtime-provided packages..."
    # shellcheck disable=SC2086
    (cd "$temp_build_dir" && rm -rf $exclude_pkgs)
    echo -e "${GREEN}  ✓${NC} Runtime-provided packages removed"
  fi

  # Create ZIP file — zip from the layer root so python/ is at the ZIP root
  echo -e "${YELLOW}  →${NC} Creating ZIP archive..."
  pushd "${TEMP_DIR}/${layer_name}" > /dev/null || return 1
  zip -r -q "$output_file" . || { popd > /dev/null; return 1; }
  popd > /dev/null || return 1

  local size
  size=$(du -h "$output_file" | cut -f1)

  echo -e "${GREEN}✓${NC} Created ${layer_name}.zip (${size})"

  return 0
}

# Function to bundle a Lambda with dependencies
# Args: lambda_name source_dir
bundle_lambda() {
  local lambda_name=$1
  local source_dir=$2
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

  # Copy shared common modules so they are importable within the Lambda package
  if [ -d "${COMMON_DIR}" ]; then
    echo -e "${YELLOW}  →${NC} Including common shared modules..."
    cp -r "${COMMON_DIR}" "${temp_build_dir}/common"
    echo -e "${GREEN}  ✓${NC} Common modules included"
  fi

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

  # Remove packages already provided by Lambda layers to stay under 262 MB limit
  local exclude_pkgs
  exclude_pkgs=$(layer_exclude_packages "$lambda_name")
  if [ -n "$exclude_pkgs" ]; then
    echo -e "${YELLOW}  →${NC} Removing layer-provided packages..."
    # shellcheck disable=SC2086
    (cd "$temp_build_dir" && rm -rf $exclude_pkgs)
    echo -e "${GREEN}  ✓${NC} Layer-provided packages removed"
  fi

  # Create ZIP file
  echo -e "${YELLOW}  →${NC} Creating ZIP archive..."
  pushd "$temp_build_dir" > /dev/null || return 1
  zip -r -q "$output_file" . || { popd > /dev/null; return 1; }
  popd > /dev/null || return 1

  local size
  size=$(du -h "$output_file" | cut -f1)

  echo -e "${GREEN}✓${NC} Created ${lambda_name}.zip (${size})"

  return 0
}

# Main execution
echo "================================================="
echo "Lambda Bundler"
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

# Create output directory and clean up any previous temp run
mkdir -p "$OUTPUT_DIR"
rm -rf "$TEMP_DIR"
echo -e "${GREEN}✓${NC} Output directory: ${OUTPUT_DIR}"
echo ""

success_count=0
fail_count=0

# --- Layers (data-pipeline) ---
if bundle_layer "bookshelf-agent" "${DATA_PIPELINE_DIR}/bookshelf-agent"; then
  success_count=$((success_count + 1))
else
  fail_count=$((fail_count + 1))
fi

# --- Data-pipeline Lambdas ---
if bundle_lambda "landing-to-raw" "${DATA_PIPELINE_DIR}/landing-to-raw"; then
  success_count=$((success_count + 1))
else
  fail_count=$((fail_count + 1))
fi

if bundle_lambda "metadata-extractor" "${DATA_PIPELINE_DIR}/metadata-extractor"; then
  success_count=$((success_count + 1))
else
  fail_count=$((fail_count + 1))
fi

# --- REST API Lambdas ---
if bundle_lambda "ops" "${RESTAPI_DIR}/ops"; then
  success_count=$((success_count + 1))
else
  fail_count=$((fail_count + 1))
fi

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
  echo -e "${GREEN}✓${NC} All bundles created successfully!"
  exit 0
else
  echo -e "${RED}✗${NC} Some bundles failed"
  exit 1
fi
