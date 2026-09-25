#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=dev-ports.sh
source "$ROOT/scripts/dev-ports.sh"
validate_platform_ports

echo "==> Starting parse-pipeline..."
"$ROOT/parse-pipeline/scripts/start.sh"

echo ""
echo "==> Starting backend..."
"$ROOT/backend/scripts/start.sh"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "==> Verifying agents API..."
for _ in $(seq 1 30); do
  if curl -sf "http://${HOST}:${PORT}/api/v1/agents" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
agent_count="$(curl -sf "http://${HOST}:${PORT}/api/v1/agents" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)"
echo "Agents available: ${agent_count}"

echo ""
echo "==> Starting frontend..."
"$ROOT/frontend/scripts/start.sh"

echo ""
echo "Platform is up."
echo "  Frontend:        http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "  Backend:         http://${HOST}:${PORT}"
echo "  Swagger:         http://${HOST}:${PORT}/docs"
echo "  Parse pipeline:  http://${PARSE_PIPELINE_HOST}:${PARSE_PIPELINE_PORT}"
