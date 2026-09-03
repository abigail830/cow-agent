#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
# shellcheck source=../scripts/dev-ports.sh
source "$REPO_ROOT/scripts/dev-ports.sh"
validate_platform_ports

RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/vite.pid"
LOG_FILE="$RUN_DIR/vite.log"
HOST="${FRONTEND_HOST:-$PLATFORM_FRONTEND_HOST}"
PORT="${FRONTEND_PORT:-$PLATFORM_FRONTEND_PORT}"

mkdir -p "$RUN_DIR"

# Ensure no stale dev server keeps serving old bundles on the same port
"$(dirname "$0")/stop.sh" >/dev/null 2>&1 || true
rm -rf "$ROOT/node_modules/.vite"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Frontend already running (pid=$old_pid). Use scripts/stop.sh first."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -d "$ROOT/node_modules" ]]; then
  echo "Dependencies not installed. Run from frontend/:"
  echo "  npm install"
  exit 1
fi

cd "$ROOT"
nohup npm run dev -- --host "$HOST" --port "$PORT" --strictPort >>"$LOG_FILE" 2>&1 &

pid=$!
echo "$pid" >"$PID_FILE"

for _ in $(seq 1 30); do
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Frontend failed to start. Last log lines:"
    tail -20 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl -sf "http://${HOST}:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "Frontend started (pid=$pid)"
echo "  URL:  http://${HOST}:${PORT}"
echo "  Log:  $LOG_FILE"
