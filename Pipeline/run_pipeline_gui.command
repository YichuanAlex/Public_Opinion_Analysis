#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi
"$PYTHON_BIN" Pipeline/pipeline_gui_server.py
