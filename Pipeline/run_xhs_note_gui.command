#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
PYTHON_BIN=""
for candidate in ".venv/bin/python" "/Library/Developer/CommandLineTools/usr/bin/python3" "/usr/bin/python3" "python3"; do
  if [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" - <<'PY' >/dev/null 2>&1
import importlib
for name in ("openpyxl", "faster_whisper", "av"):
    importlib.import_module(name)
try:
    importlib.import_module("Vision")
except Exception:
    pass
PY
    then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
echo "Using Python: $("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"
"$PYTHON_BIN" Pipeline/pipeline_gui_server.py
