#!/usr/bin/env bash
# ============================================================
#  start.sh - Khoi dong AI Path Backend (Linux / macOS)
#  Su dung: ./start.sh
# ============================================================
set -e

# Chuyen den thu muc chua script nay
cd "$(dirname "$0")"

# Force UTF-8 cho Python
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

echo "[start.sh] Khoi dong AI Path Backend tai http://127.0.0.1:8000 ..."

# Chay server (hardcoded localhost:8000 trong app/main.py)
python3 -m app.main "$@"
