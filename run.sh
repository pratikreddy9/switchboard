#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_NODE_ROOT="$PWD"

echo "Switchboard"
echo "1) Control Center"
echo "2) Node"
printf "Select mode [1]: "
read -r MODE_INPUT
MODE="${MODE_INPUT:-1}"

case "$MODE" in
  1)
    echo "Control Center"
    echo "1) Start"
    echo "2) Restart"
    echo "3) Status"
    echo "4) Logs"
    printf "Select action [1]: "
    read -r ACTION_INPUT
    ACTION="${ACTION_INPUT:-1}"
    case "$ACTION" in
      1) exec "$ROOT_DIR/framework.sh" start ;;
      2) exec "$ROOT_DIR/framework.sh" restart ;;
      3) exec "$ROOT_DIR/framework.sh" status ;;
      4) exec "$ROOT_DIR/framework.sh" logs ;;
      *) echo "Invalid action"; exit 1 ;;
    esac
    ;;
  2)
    echo "Node"
    printf "Project root [$DEFAULT_NODE_ROOT]: "
    read -r PROJECT_ROOT_INPUT
    PROJECT_ROOT="${PROJECT_ROOT_INPUT:-$DEFAULT_NODE_ROOT}"
    printf "Host [127.0.0.1]: "
    read -r HOST_INPUT
    HOST="${HOST_INPUT:-127.0.0.1}"
    printf "Port [8010]: "
    read -r PORT_INPUT
    PORT="${PORT_INPUT:-8010}"
    echo "1) Start"
    echo "2) Stop"
    echo "3) Status"
    echo "4) Logs"
    printf "Select action [1]: "
    read -r NODE_ACTION_INPUT
    NODE_ACTION="${NODE_ACTION_INPUT:-1}"
    case "$NODE_ACTION" in
      1) exec "$ROOT_DIR/.venv/bin/switchboard" node start --project-root "$PROJECT_ROOT" --host "$HOST" --port "$PORT" ;;
      2) exec "$ROOT_DIR/.venv/bin/switchboard" node stop --project-root "$PROJECT_ROOT" --port "$PORT" ;;
      3) exec "$ROOT_DIR/.venv/bin/switchboard" node status --project-root "$PROJECT_ROOT" --port "$PORT" ;;
      4) exec "$ROOT_DIR/.venv/bin/switchboard" node logs --project-root "$PROJECT_ROOT" ;;
      *) echo "Invalid action"; exit 1 ;;
    esac
    ;;
  *)
    echo "Invalid mode"
    exit 1
    ;;
esac
