#!/bin/bash
set -e

# Create temp directory
TEST_DATA_DIR=$(mktemp -d /tmp/dazflow-playwright-test-XXXXXX)
echo "Using test data directory: $TEST_DATA_DIR"

# Create required subdirectories
mkdir -p "$TEST_DATA_DIR/workflows"
mkdir -p "$TEST_DATA_DIR/local/work/output"
mkdir -p "$TEST_DATA_DIR/local/work/stats"
mkdir -p "$TEST_DATA_DIR/local/work/queue"
mkdir -p "$TEST_DATA_DIR/local/work/executions"
mkdir -p "$TEST_DATA_DIR/local/work/indexes"

# Copy sample workflow
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/sample.json" "$TEST_DATA_DIR/workflows/"

# Cleanup on exit
cleanup() {
    echo "Cleaning up $TEST_DATA_DIR"
    rm -rf "$TEST_DATA_DIR"
}
trap cleanup EXIT

# Start server with test data directory
export DAZFLOW_DATA_DIR="$TEST_DATA_DIR"
export DAZFLOW_PORT=31416
export DAZFLOW_EXECUTIONS_CACHE_INTERVAL=1
python -m uvicorn src.api:app --host 0.0.0.0 --port 31416
