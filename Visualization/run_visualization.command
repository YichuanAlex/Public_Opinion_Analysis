#!/bin/bash
set -e
cd "$(dirname "$0")/.."

PYTHON_BIN="${PIPELINE_PYTHON:-python3}"
exec "$PYTHON_BIN" Visualization/server.py --port 8765
