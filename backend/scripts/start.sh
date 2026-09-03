#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
# shellcheck source=../scripts/dev-ports.sh
source "$REPO_ROOT/scripts/dev-ports.sh"
validate_platform_ports

RUN_DIR="$ROOT/.run"
PID_FILE="$RUN_DIR/uvicorn.pid"
LOG_FILE="$RUN_DIR/uvicorn.log"
VENV="$ROOT/.venv"
HOST="${HOST:-$PLATFORM_BACKEND_HOST}"
PORT="${PORT:-$PLATFORM_BACKEND_PORT}"

mkdir -p "$RUN_DIR"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Backend already running (pid=$old_pid). Use scripts/stop.sh first."
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "Virtualenv not found. Run from backend/:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

# MCP stdio agents (YL-Worker, SP analysts) spawn `npx`; background start must see Node on PATH.
if [[ -z "${NPX_PATH:-}" ]]; then
  if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  fi
  if command -v npx >/dev/null 2>&1; then
    NPX_PATH="$(command -v npx)"
    export NPX_PATH
    export PATH="$(dirname "$NPX_PATH"):${PATH}"
  else
    echo "WARNING: npx not found — MCP agents (YL-Worker-001, SP analysts) will fail at chat time." >&2
    echo "  Install Node.js (https://nodejs.org) or ensure nvm is loaded before ./scripts/start.sh" >&2
  fi
fi

cd "$ROOT"
nohup "$VENV/bin/uvicorn" app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  >>"$LOG_FILE" 2>&1 &

pid=$!
echo "$pid" >"$PID_FILE"

ready=0
max_wait="${BACKEND_STARTUP_WAIT:-120}"
for i in $(seq 1 "$max_wait"); do
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Backend failed to start. Last log lines:"
    tail -20 "$LOG_FILE" 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
  fi
  if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if (( i % 20 == 0 )); then
    echo "  Still waiting for backend health (${i}/${max_wait})..."
  fi
  sleep 0.5
done

if [[ "$ready" -ne 1 ]]; then
  echo "Backend did not become healthy in time (${max_wait} x 0.5s)."
  echo "If DATABASE_URL points to a remote Postgres, sync on startup can be slow."
  echo "Set BACKEND_STARTUP_WAIT=240 for more headroom. Last log lines:"
  tail -20 "$LOG_FILE" 2>/dev/null || true
  kill "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "Backend started (pid=$pid)"
echo "  URL:  http://${HOST}:${PORT}"
echo "  Log:  $LOG_FILE"
