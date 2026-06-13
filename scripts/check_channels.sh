#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
API_HOST="${FENGBIAO_API_HOST:-127.0.0.1}"
API_PORT="${FENGBIAO_API_PORT:-8765}"
WEB_URL="${FENGBIAO_WEB_URL:-http://127.0.0.1:5173}"
API_URL="http://${API_HOST}:${API_PORT}"
LOG_DIR="${ROOT}/data/logs"
TMP_DIR="${TMPDIR:-/tmp}/fengbiao-channel-check"
STARTED_API_PID=""

mkdir -p "$LOG_DIR" "$TMP_DIR"

cleanup() {
  if [[ -n "$STARTED_API_PID" ]] && kill -0 "$STARTED_API_PID" 2>/dev/null; then
    kill "$STARTED_API_PID" 2>/dev/null || true
    wait "$STARTED_API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

require_json_count() {
  local file="$1"
  "$PYTHON_BIN" - "$file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
counts = payload.get("counts", {})
print(f"samples={counts.get('samples')} generatedAt={payload.get('generatedAt')}")
PY
}

wait_for_api() {
  for _ in $(seq 1 30); do
    if curl -fsS "${API_URL}/api/health" >"${TMP_DIR}/health.json"; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

cd "$ROOT"

if ! curl -fsS "${API_URL}/api/health" >"${TMP_DIR}/health.json"; then
  PYTHONPATH=src "$PYTHON_BIN" -m fengbiao.cli sync-server --host "$API_HOST" --port "$API_PORT" >"${LOG_DIR}/sync-server-check.log" 2>&1 &
  STARTED_API_PID="$!"
  wait_for_api
fi

echo "api_health_ok $(tr -d '\n' <"${TMP_DIR}/health.json")"

curl -fsS "${API_URL}/api/snapshot?export=1" >"${TMP_DIR}/api-snapshot.json"
echo "api_snapshot_ok $(require_json_count "${TMP_DIR}/api-snapshot.json")"

if curl -fsS "${WEB_URL}/" >"${TMP_DIR}/web-root.html"; then
  echo "web_root_ok bytes=$(wc -c <"${TMP_DIR}/web-root.html" | tr -d ' ')"

  curl -fsS "${WEB_URL}/api/snapshot" >"${TMP_DIR}/vite-proxy-snapshot.json"
  echo "vite_proxy_snapshot_ok $(require_json_count "${TMP_DIR}/vite-proxy-snapshot.json")"

  curl -fsS "${WEB_URL}/fengbiao-snapshot.json" >"${TMP_DIR}/static-snapshot.json"
  echo "static_snapshot_ok $(require_json_count "${TMP_DIR}/static-snapshot.json")"
else
  echo "web_root_skipped ${WEB_URL} is not reachable"
fi
