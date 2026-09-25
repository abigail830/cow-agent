#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
# shellcheck source=../scripts/dev-ports.sh
source "$REPO_ROOT/scripts/dev-ports.sh"

PID_FILE="$ROOT/.run/parse-pipeline.pid"
PORT="${PARSE_PIPELINE_PORT:-$PLATFORM_PARSE_PIPELINE_PORT}"

stop_pid() {
  local pid="$1"
  if ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi
  echo "Stopping parse-pipeline (pid=$pid)..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.5
  done
  echo "Force killing pid=$pid"
  kill -9 "$pid" 2>/dev/null || true
}

stopped=0

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if stop_pid "$pid" || ! kill -0 "$pid" 2>/dev/null; then
    stopped=1
  fi
  rm -f "$PID_FILE"
fi

for port_pid in $(lsof -ti:"$PORT" 2>/dev/null || true); do
  stop_pid "$port_pid" || kill -9 "$port_pid" 2>/dev/null || true
  stopped=1
done

if [[ "$stopped" -eq 1 ]]; then
  echo "parse-pipeline stopped."
else
  echo "parse-pipeline is not running."
fi
