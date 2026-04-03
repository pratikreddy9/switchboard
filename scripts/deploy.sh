#!/usr/bin/env bash
# -------------------------------------------------------
# deploy.sh — install Switchboard from GitHub and restart
#
# Usage:
#   ./scripts/deploy.sh                   # latest main
#   ./scripts/deploy.sh v0.1.8            # specific tag
#   ./scripts/deploy.sh my-branch         # specific branch
#
# Requires: git, uv (https://github.com/astral-sh/uv)
# -------------------------------------------------------
set -euo pipefail

REPO="https://github.com/pratikreddy9/switchboard.git"
REF="${1:-main}"
INSTALL_DIR="$HOME/.local/share/switchboard-deploy"
LOG_DIR="/tmp"

# ── Resolve the install target ──────────────────────────
# If REF looks like a tag (v*) use archive URL for a clean install;
# otherwise clone/pull the branch.
echo "▸ Fetching switchboard @ $REF from GitHub..."

if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" checkout "$REF"
  git -C "$INSTALL_DIR" reset --hard "origin/$REF" 2>/dev/null \
    || git -C "$INSTALL_DIR" reset --hard "$REF"
else
  rm -rf "$INSTALL_DIR"
  git clone --branch "$REF" --depth 1 "$REPO" "$INSTALL_DIR"
fi

VERSION=$(python3 -c "import tomllib; d=tomllib.load(open('$INSTALL_DIR/pyproject.toml','rb')); print(d['project']['version'])")
echo "  → cloned v$VERSION"

# ── Install Python package via uv ───────────────────────
echo "▸ Installing Python package with uv..."
~/.local/bin/uv tool install "$INSTALL_DIR" --force

# ── Build frontend ──────────────────────────────────────
echo "▸ Building frontend..."
# Use node from the project .venv shim if present, else system node
NODE=$(command -v node 2>/dev/null || echo "/usr/local/bin/node")
NPM=$(command -v npm 2>/dev/null || echo "/usr/local/bin/npm")

cd "$INSTALL_DIR"
# Install node deps if needed
if [ ! -d "node_modules" ]; then
  "$NPM" install
fi
PATH="$(dirname "$NODE"):$PATH" "$NODE" node_modules/.bin/tsc --noEmit
PATH="$(dirname "$NODE"):$PATH" "$NODE" node_modules/.bin/vite build

echo "▸ Copying built frontend into package..."
# The switchboard static dir is baked into the installed package;
# copy the fresh dist into the uv tool venv's switchboard/static
UV_SWITCHBOARD=$(~/.local/bin/uv tool run switchboard --help 2>/dev/null | head -1 || true)
STATIC_TARGET=$(python3 -c "
import importlib.util, pathlib
spec = importlib.util.find_spec('switchboard')
print(pathlib.Path(spec.origin).parent / 'static' / 'app')
" 2>/dev/null || echo "")

if [ -n "$STATIC_TARGET" ]; then
  rm -rf "$STATIC_TARGET"
  cp -r "$INSTALL_DIR/dist" "$STATIC_TARGET"
  echo "  → static assets deployed to $STATIC_TARGET"
fi

# ── Restart servers ─────────────────────────────────────
echo "▸ Stopping existing Switchboard processes..."
pkill -f "uvicorn switchboard.api:app" 2>/dev/null || true
pkill -f "switchboard.cli node serve"  2>/dev/null || true
sleep 1

# Detect project root (the live checkout, not the deploy temp dir)
LIVE_ROOT="${SWITCHBOARD_PROJECT_ROOT:-$HOME/Desktop/dashboard}"

echo "▸ Starting control-center API  → http://127.0.0.1:8009"
~/.local/bin/uvicorn switchboard.api:app \
  --host 127.0.0.1 --port 8009 \
  >> "$LOG_DIR/switchboard-8009.log" 2>&1 &

echo "▸ Starting node server         → http://127.0.0.1:8010"
~/.local/bin/switchboard node serve \
  --project-root "$LIVE_ROOT" \
  --host 127.0.0.1 --port 8010 \
  >> "$LOG_DIR/switchboard-8010.log" 2>&1 &

sleep 2
V1=$(curl -sf http://127.0.0.1:8009/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "unreachable")
V2=$(curl -sf http://127.0.0.1:8010/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "unreachable")

echo ""
echo "  8009 (control center) → v$V1"
echo "  8010 (node server)    → v$V2"
echo ""
echo "✓ Deployed v$VERSION from GitHub."
