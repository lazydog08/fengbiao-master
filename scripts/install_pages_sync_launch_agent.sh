#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_NAME="com.lazydog.fengbiao-pages-sync.plist"
SOURCE="${ROOT}/ops/launchagents/${PLIST_NAME}"
TARGET="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
UID_VALUE="$(id -u)"
RUNTIME_ROOT="${FENGBIAO_PAGES_SYNC_ROOT:-${HOME}/Library/Application Support/fengbiao-master-runtime}"
REPO_URL="${FENGBIAO_REPO_URL:-$(git -C "$ROOT" config --get remote.origin.url)}"
RUN_NOW=0
SEED_RUNTIME_DATA="${FENGBIAO_SEED_RUNTIME_DATA:-missing}"

usage() {
  printf 'Usage: %s [--run-now]\n' "$(basename "$0")"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-now)
      RUN_NOW=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs" "${ROOT}/data/logs" "$(dirname "$RUNTIME_ROOT")"

if [[ -z "$REPO_URL" ]]; then
  echo "missing git remote origin url" >&2
  exit 2
fi

if [[ ! -d "${RUNTIME_ROOT}/.git" ]]; then
  git clone "$REPO_URL" "$RUNTIME_ROOT"
else
  git -C "$RUNTIME_ROOT" fetch origin main
  git -C "$RUNTIME_ROOT" checkout main
  git -C "$RUNTIME_ROOT" pull --ff-only origin main
fi

mkdir -p "${RUNTIME_ROOT}/data/db" "${RUNTIME_ROOT}/data/covers"
PYTHONPATH="${ROOT}/src" python3 - "$ROOT" "$RUNTIME_ROOT" "$SEED_RUNTIME_DATA" <<'PY'
import json
import sys

from fengbiao.runtime_data import sync_runtime_data

result = sync_runtime_data(sys.argv[1], sys.argv[2], force=sys.argv[3] == "1")
print(json.dumps({"runtimeDataSync": result}, ensure_ascii=False, sort_keys=True))
PY

cp "$SOURCE" "$TARGET"
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:FENGBIAO_CANONICAL_DATA_ROOT ${ROOT}" "$TARGET" >/dev/null 2>&1 \
  || /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:FENGBIAO_CANONICAL_DATA_ROOT string ${ROOT}" "$TARGET" >/dev/null

launchctl bootout "gui/${UID_VALUE}" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID_VALUE}" "$TARGET"
launchctl enable "gui/${UID_VALUE}/${PLIST_NAME%.plist}"

if [[ "$RUN_NOW" -eq 1 ]]; then
  launchctl kickstart -k "gui/${UID_VALUE}/${PLIST_NAME%.plist}" || true
fi

echo "installed=${TARGET}"
echo "runtime=${RUNTIME_ROOT}"
