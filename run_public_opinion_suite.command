#!/bin/bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VISUALIZATION_PORT="${VISUALIZATION_PORT:-8765}"
PIPELINE_GUI_PORT="${PIPELINE_GUI_PORT:-8766}"

choose_python() {
  local candidates=()
  if [[ -n "${PIPELINE_PYTHON:-}" ]]; then
    candidates+=("$PIPELINE_PYTHON")
  fi
  candidates+=(
    "$PROJECT_DIR/.venv/bin/python"
    "/Library/Developer/CommandLineTools/usr/bin/python3"
    "/usr/bin/python3"
    "$(command -v python3.9 || true)"
    "$(command -v python3 || true)"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -z "$candidate" ]] && continue
    [[ "$candidate" == */* && ! -x "$candidate" ]] && continue
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
print(sys.executable)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf 'python3\n'
}

PYTHON_BIN="$(choose_python)"
VISUALIZATION_URL="http://127.0.0.1:${VISUALIZATION_PORT}/"
urlencode() {
  "$PYTHON_BIN" - "$1" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
}

PIPELINE_URL="http://127.0.0.1:${PIPELINE_GUI_PORT}/?visualization=$(urlencode "$VISUALIZATION_URL")"
VISUALIZATION_ENTRY="${VISUALIZATION_URL}?pipeline=$(urlencode "$PIPELINE_URL")"

cleanup() {
  if [[ -n "${VIS_PID:-}" ]]; then
    kill "$VIS_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${PIPE_PID:-}" ]]; then
    kill "$PIPE_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "Using Python: $PYTHON_BIN"
echo "Starting Visualization: $VISUALIZATION_URL"
"$PYTHON_BIN" Visualization/server.py --host 127.0.0.1 --port "$VISUALIZATION_PORT" &
VIS_PID=$!

echo "Starting Pipeline GUI: http://127.0.0.1:${PIPELINE_GUI_PORT}/"
PIPELINE_GUI_PORT="$PIPELINE_GUI_PORT" PIPELINE_GUI_NO_OPEN=1 "$PYTHON_BIN" Pipeline/pipeline_gui_server.py &
PIPE_PID=$!

sleep 1.2
open "$VISUALIZATION_ENTRY" >/dev/null 2>&1 || true

echo
echo "Public Opinion Suite is running."
echo "Visualization homepage: ${VISUALIZATION_ENTRY}"
echo "Pipeline workspace: ${PIPELINE_URL}"
echo "Press Ctrl+C in this window to stop both services."

wait
