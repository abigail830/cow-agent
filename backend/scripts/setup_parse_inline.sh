#!/usr/bin/env bash
# Prepare local parse-pipeline HTTP service (same path as future standalone deploy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PARSE_DIR="$ROOT/parse-pipeline"
BACKEND_DIR="$ROOT/backend"
BACKEND_ENV="$BACKEND_DIR/.env"

echo "==> parse-pipeline venv + deps ($PARSE_DIR)"
cd "$PARSE_DIR"
if command -v uv >/dev/null 2>&1; then
  if [[ ! -d .venv ]]; then
    uv venv .venv --python 3.11
  fi
  uv pip install -e ".[dev]"
else
  if [[ ! -d .venv ]]; then
    python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
  fi
  .venv/bin/pip install -U pip
  .venv/bin/pip install -e ".[dev]"
fi

echo "==> verify parse-pipeline CLI"
.venv/bin/parse-pipeline run-job --help >/dev/null

if [[ ! -f "$PARSE_DIR/.env" ]]; then
  cp "$PARSE_DIR/.env.example" "$PARSE_DIR/.env"
  echo "Created parse-pipeline/.env — set DOCUMENT_MIND_* and PARSE_PIPELINE_API_KEYS."
fi

# Extract first API key for agent-platform caller (caller_id:key)
SERVICE_KEY=""
if [[ -f "$PARSE_DIR/.env" ]]; then
  line=$(grep -E '^PARSE_PIPELINE_API_KEYS=' "$PARSE_DIR/.env" | head -1 || true)
  if [[ -n "$line" ]]; then
    pair=$(echo "$line" | cut -d= -f2- | cut -d, -f1)
    SERVICE_KEY=$(echo "$pair" | cut -d: -f2-)
  fi
fi

mkdir -p "$BACKEND_DIR/data/chat-attachments"

cat <<EOF

Parse service environment ready.

Start the full stack (parse-pipeline + backend + frontend):

  ./scripts/start.sh

Or manually: parse-pipeline/scripts/start.sh then backend/scripts/start.sh
(PARSE_PIPELINE_PUBLIC_BASE_URL must match backend, default http://127.0.0.1:8000)

Backend .env (service dispatch — HTTP + webhook, unified with standalone deploy):

  PARSE_PIPELINE_DISPATCH=service
  PARSE_PIPELINE_SERVICE_URL=http://127.0.0.1:8091
  PARSE_PIPELINE_PUBLIC_BASE_URL=http://127.0.0.1:8000
  PARSE_PIPELINE_SERVICE_API_KEY=${SERVICE_KEY:-<copy from parse-pipeline/.env PARSE_PIPELINE_API_KEYS>}
  PARSE_PIPELINE_SERVICE_CALLER_ID=agent-platform
  OFFICE_MARKITDOWN_ENABLED=true

parse-pipeline/.env: DOCUMENT_MIND_* for PDF; OFFICE_MARKITDOWN_ENABLED=true for docx.

Legacy PARSE_PIPELINE_DISPATCH=inline (subprocess) is deprecated.

EOF
