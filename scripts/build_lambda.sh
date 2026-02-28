#!/usr/bin/env bash
# File: scripts/build_lambda.sh
# Builds the Lambda deployment zip using Docker for Linux compatibility.
#
# Usage:
#   ./scripts/build_lambda.sh
#
# Output:
#   dist/lambda_package.zip — ready for Terraform deploy.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_ZIP="${PROJECT_ROOT}/dist/lambda_package.zip"
DOCKER_IMAGE="python:3.13-slim"

echo "==> Cleaning previous build..."
rm -rf "${PROJECT_ROOT}/dist"
mkdir -p "${PROJECT_ROOT}/dist"

echo "==> Building Lambda package via Docker (linux/amd64)..."
docker run --rm \
    --platform linux/amd64 \
    -v "${PROJECT_ROOT}:/build" \
    -w /build \
    "${DOCKER_IMAGE}" \
    /bin/bash -c '
        set -e
        apt-get update -qq && apt-get install -y -qq zip > /dev/null
        mkdir -p /tmp/package

        # Install dependencies into package directory
        pip install --target /tmp/package -r requirements.txt --quiet 2>/dev/null

        # Copy application code
        cp -r bot /tmp/package/bot
        cp lambda_handler.py /tmp/package/lambda_handler.py
        mkdir -p /tmp/package/data

        # Prune unnecessary files
        find /tmp/package -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find /tmp/package -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        find /tmp/package -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
        find /tmp/package -type f -name "*.pyc" -delete 2>/dev/null || true

        # Create zip
        cd /tmp/package
        yum install -y zip > /dev/null 2>&1 || true
        zip -r /build/dist/lambda_package.zip . -q
    '

PACKAGE_SIZE=$(du -sh "${OUTPUT_ZIP}" | cut -f1)
echo "==> Build complete: ${OUTPUT_ZIP} (${PACKAGE_SIZE})"
