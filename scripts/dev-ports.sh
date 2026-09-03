#!/usr/bin/env bash
# 开发环境端口约定 — Agent Platform 单栈。

# Platform（scripts/start.sh / frontend / backend）
export PLATFORM_BACKEND_HOST="${PLATFORM_BACKEND_HOST:-127.0.0.1}"
export PLATFORM_BACKEND_PORT="${PLATFORM_BACKEND_PORT:-8000}"
export PLATFORM_FRONTEND_HOST="${PLATFORM_FRONTEND_HOST:-127.0.0.1}"
export PLATFORM_FRONTEND_PORT="${PLATFORM_FRONTEND_PORT:-5173}"

# 兼容旧变量名（platform start 脚本仍使用 HOST / PORT / FRONTEND_*）
export HOST="${HOST:-$PLATFORM_BACKEND_HOST}"
export PORT="${PORT:-$PLATFORM_BACKEND_PORT}"
export FRONTEND_HOST="${FRONTEND_HOST:-$PLATFORM_FRONTEND_HOST}"
export FRONTEND_PORT="${FRONTEND_PORT:-$PLATFORM_FRONTEND_PORT}"

_assert_distinct_ports() {
  local label="$1"
  shift
  local -a ports=("$@")
  local i j
  for ((i = 0; i < ${#ports[@]}; i++)); do
    for ((j = i + 1; j < ${#ports[@]}; j++)); do
      if [[ "${ports[i]}" == "${ports[j]}" ]]; then
        echo "ERROR: ${label} — port ${ports[i]} is assigned more than once." >&2
        exit 1
      fi
    done
  done
}

validate_platform_ports() {
  _assert_distinct_ports "platform port map" \
    "$PLATFORM_BACKEND_PORT" \
    "$PLATFORM_FRONTEND_PORT"
}

port_owner_hint() {
  local port="$1"
  case "$port" in
    "$PLATFORM_BACKEND_PORT") echo "platform backend (uvicorn)" ;;
    "$PLATFORM_FRONTEND_PORT") echo "platform frontend (vite)" ;;
    *) echo "unknown process" ;;
  esac
}

assert_port_available_or_owned() {
  local port="$1"
  local expected_label="$2"
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  echo "WARNING: Port $port already in use ($expected_label expected, may be $(port_owner_hint "$port"))." >&2
  echo "  PIDs: $pids — run ./scripts/stop.sh if needed." >&2
}
