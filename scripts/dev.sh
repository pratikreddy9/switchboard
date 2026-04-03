#!/usr/bin/env bash
# -------------------------------------------------------
# dev.sh — restart all local Switchboard processes
# Usage: ./scripts/dev.sh
# -------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
LOG_DIR="/tmp"

echo "▸ Stopping existing Switchboard processes..."
pkill -f "uvicorn switchboard.api:app" 2>/dev/null || true
pkill -f "switchboard.cli node serve"  2>/dev/null || true
sleep 1

echo "▸ Starting control-center API  → http://127.0.0.1:8009"
"$VENV/bin/uvicorn" switchboard.api:app \
  --host 127.0.0.1 --port 8009 \
  >> "$LOG_DIR/switchboard-8009.log" 2>&1 &

echo "▸ Starting node server         → http://127.0.0.1:8010"
"$VENV/bin/python3" -m switchboard.cli node serve \
  --project-root "$ROOT" \
  --host 127.0.0.1 --port 8010 \
  >> "$LOG_DIR/switchboard-8010.log" 2>&1 &

# Wait and confirm both are up
sleep 2
V1=$(curl -sf http://127.0.0.1:8009/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "unreachable")
V2=$(curl -sf http://127.0.0.1:8010/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "unreachable")

echo ""
echo "  8009 (control center) → v$V1"
echo "  8010 (node server)    → v$V2"
echo ""
echo "✓ Done. Vite dev server (5173) is NOT managed here — run separately:"
echo "  cd $ROOT && .venv/bin/node node_modules/.bin/vite --host 127.0.0.1 --port 5173"
