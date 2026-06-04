#!/usr/bin/env bash
# ============================================================
#  start-cloudflare.sh - Chay backend + Cloudflare Tunnel
#  Su dung: ./start-cloudflare.sh
#  Tao public URL qua Cloudflare Tunnel (*.trycloudflare.com)
# ============================================================
set -e

cd "$(dirname "$0")"

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

# Use project venv if available
VENV="$(dirname "$(dirname "$0")")/.venv"
if [ -f "$VENV/bin/python3" ]; then
  export PATH="$VENV/bin:$PATH"
  echo "[cloudflare] Using venv: $VENV"
fi

# Cleanup on exit
cleanup() {
  echo ""
  echo "[cloudflare] Shutting down..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $TUNNEL_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend in background
echo "[1/2] Starting backend on http://127.0.0.1:8000 ..."
python3 -m app.main &
BACKEND_PID=$!

# Wait for backend to be ready
echo "[1/2] Waiting for backend to start..."
for i in $(seq 1 20); do
  if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "[1/2] Backend is ready!"
    break
  fi
  sleep 1
done

# Start Cloudflare Tunnel
echo "[2/2] Starting Cloudflare Tunnel..."
echo "[2/2] Your public URL will appear below (look for trycloudflare.com):"
echo "-------------------------------------------------------------------"
cloudflared tunnel --url http://127.0.0.1:8000 &
TUNNEL_PID=$!

# Keep running
wait $BACKEND_PID
