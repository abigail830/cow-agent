#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
# shellcheck source=../scripts/dev-ports.sh
source "$REPO_ROOT/scripts/dev-ports.sh"
validate_platform_ports

RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/parse-pipeline.pid"
LOG_FILE="$RUN_DIR/parse-pipeline.log"
VENV="$ROOT/.venv"
HOST="${PARSE_PIPELINE_HOST:-$PLATFORM_PARSE_PIPELINE_HOST}"
PORT="${PARSE_PIPELINE_PORT:-$PLATFORM_PARSE_PIPELINE_PORT}"

mkdir -p "$RUN_DIR"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "parse-pipeline already running (pid=$old_pid). Use scripts/stop.sh first."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -x "$VENV/bin/parse-pipeline" ]]; then
  echo "parse-pipeline venv not found. Run:"
  echo "  $REPO_ROOT/backend/scripts/setup_parse_inline.sh"
  exit 1
fi

cd "$ROOT"
export HOST PORT
nohup "$VENV/bin/parse-pipeline" serve >>"$LOG_FILE" 2>&1 &

pid=$!
echo "$pid" >"$PID_FILE"

ready=0
for _ in $(seq 1 60); do
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "parse-pipeline failed to start. Last log lines:"
    tail -20 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.5
done

if [[ "$ready" -ne 1 ]]; then
  echo "parse-pipeline did not become healthy in time."
  tail -20 "$LOG_FILE" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "parse-pipeline started (pid=$pid)"
echo "  URL:  http://${HOST}:${PORT}"
echo "  Log:  $LOG_FILE"
