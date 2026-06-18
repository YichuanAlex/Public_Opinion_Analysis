#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
python3 Pipeline/xhs_gui_server.py
