#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/state/run"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_PORT="${SWITCHBOARD_BACKEND_PORT:-8009}"
FRONTEND_PORT="${SWITCHBOARD_FRONTEND_PORT:-5173}"
BACKEND_HOST="${SWITCHBOARD_BACKEND_HOST:-127.0.0.1}"
FRONTEND_HOST="${SWITCHBOARD_FRONTEND_HOST:-127.0.0.1}"
BACKEND_RELOAD="${SWITCHBOARD_BACKEND_RELOAD:-0}"

mkdir -p "$LOG_DIR" "$RUN_DIR"

pid_on_port() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

read_pid() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    cat "$pid_file"
  fi
}

is_running() {
  local pid="$1"
  if [ -z "${pid:-}" ]; then
    return 1
  fi
  kill -0 "$pid" 2>/dev/null
}

cleanup_pid_file() {
  local pid_file="$1"
  local pid
  pid="$(read_pid "$pid_file")"
  if [ -n "${pid:-}" ] && ! is_running "$pid"; then
    rm -f "$pid_file"
  fi
}

start_backend() {
  cleanup_pid_file "$BACKEND_PID_FILE"
  local pid
  pid="$(read_pid "$BACKEND_PID_FILE")"
  if is_running "$pid"; then
    echo "Backend already running (pid $pid)"
    return
  fi
  local existing_port_pid
  existing_port_pid="$(pid_on_port "$BACKEND_PORT")"
  if [ -n "${existing_port_pid:-}" ]; then
    echo "Backend port $BACKEND_PORT is already in use by pid $existing_port_pid"
    echo "Run ./framework.sh stop or manually stop the old backend first."
    return 1
  fi

  local reload_args=()
  if [ "$BACKEND_RELOAD" = "1" ]; then
    reload_args+=(--reload)
  fi

  echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT"
  (
    cd "$ROOT_DIR"
    if [ "${#reload_args[@]}" -gt 0 ]; then
      nohup ./.venv/bin/python -m uvicorn switchboard.api:app \
        --host "$BACKEND_HOST" \
        --port "$BACKEND_PORT" \
        "${reload_args[@]}" \
        >>"$BACKEND_LOG" 2>&1 &
    else
      nohup ./.venv/bin/python -m uvicorn switchboard.api:app \
        --host "$BACKEND_HOST" \
        --port "$BACKEND_PORT" \
        >>"$BACKEND_LOG" 2>&1 &
    fi
    echo $! > "$BACKEND_PID_FILE"
  )
}

start_frontend() {
  cleanup_pid_file "$FRONTEND_PID_FILE"
  local pid
  pid="$(read_pid "$FRONTEND_PID_FILE")"
  if is_running "$pid"; then
    echo "Frontend already running (pid $pid)"
    return
  fi
  local existing_port_pid
  existing_port_pid="$(pid_on_port "$FRONTEND_PORT")"
  if [ -n "${existing_port_pid:-}" ]; then
    echo "Frontend port $FRONTEND_PORT is already in use by pid $existing_port_pid"
    echo "Run ./framework.sh stop or manually stop the old frontend first."
    return 1
  fi

  echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT"
  (
    cd "$ROOT_DIR"
    nohup npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
      >>"$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
  )
}

stop_one() {
  local pid_file="$1"
  local label="$2"
  local port="$3"
  cleanup_pid_file "$pid_file"
  local pid
  pid="$(read_pid "$pid_file")"
  if is_running "$pid"; then
    echo "Stopping $label (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if is_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
  local port_pid
  port_pid="$(pid_on_port "$port")"
  if [ -n "${port_pid:-}" ]; then
    echo "Stopping $label listener on port $port (pid $port_pid)"
    kill "$port_pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$port_pid" 2>/dev/null; then
      kill -9 "$port_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
    return
  fi
  echo "$label not running"
}

status_one() {
  local pid_file="$1"
  local label="$2"
  local port="$3"
  cleanup_pid_file "$pid_file"
  local pid
  pid="$(read_pid "$pid_file")"
  if is_running "$pid"; then
    echo "$label: running (pid $pid)"
    return
  fi
  local port_pid
  port_pid="$(pid_on_port "$port")"
  if [ -n "${port_pid:-}" ]; then
    echo "$label: running on port $port (pid $port_pid, unmanaged)"
  else
    echo "$label: stopped"
  fi
}

tail_logs() {
  touch "$BACKEND_LOG" "$FRONTEND_LOG"
  tail -n 40 -f "$BACKEND_LOG" "$FRONTEND_LOG"
}

usage() {
  cat <<'EOF'
Usage: ./framework.sh <command>

Commands:
  start      Start backend and frontend in nohup mode
  stop       Stop backend and frontend
  restart    Restart backend and frontend
  status     Show backend/frontend pid state
  logs       Tail backend and frontend logs
  backend    Start backend only
  frontend   Start frontend only
EOF
}

case "${1:-}" in
  start)
    start_backend
    start_frontend
    ;;
  stop)
    stop_one "$FRONTEND_PID_FILE" "Frontend" "$FRONTEND_PORT"
    stop_one "$BACKEND_PID_FILE" "Backend" "$BACKEND_PORT"
    ;;
  restart)
    stop_one "$FRONTEND_PID_FILE" "Frontend" "$FRONTEND_PORT"
    stop_one "$BACKEND_PID_FILE" "Backend" "$BACKEND_PORT"
    start_backend
    start_frontend
    ;;
  status)
    status_one "$BACKEND_PID_FILE" "Backend" "$BACKEND_PORT"
    status_one "$FRONTEND_PID_FILE" "Frontend" "$FRONTEND_PORT"
    echo "Backend log: $BACKEND_LOG"
    echo "Frontend log: $FRONTEND_LOG"
    ;;
  logs)
    tail_logs
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  *)
    usage
    exit 1
    ;;
esac
