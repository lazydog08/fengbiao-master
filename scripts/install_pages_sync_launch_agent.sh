#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_NAME="com.lazydog.fengbiao-pages-sync.plist"
SOURCE="${ROOT}/ops/launchagents/${PLIST_NAME}"
TARGET="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
UID_VALUE="$(id -u)"
RUN_NOW=0

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

mkdir -p "${HOME}/Library/LaunchAgents"
cp "$SOURCE" "$TARGET"

launchctl bootout "gui/${UID_VALUE}" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID_VALUE}" "$TARGET"
launchctl enable "gui/${UID_VALUE}/${PLIST_NAME%.plist}"

if [[ "$RUN_NOW" -eq 1 ]]; then
  launchctl kickstart -k "gui/${UID_VALUE}/${PLIST_NAME%.plist}" || true
fi

echo "installed=${TARGET}"
