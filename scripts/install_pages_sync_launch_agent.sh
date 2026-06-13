#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_NAME="com.lazydog.fengbiao-pages-sync.plist"
SOURCE="${ROOT}/ops/launchagents/${PLIST_NAME}"
TARGET="${HOME}/Library/LaunchAgents/${PLIST_NAME}"
UID_VALUE="$(id -u)"

mkdir -p "${HOME}/Library/LaunchAgents"
cp "$SOURCE" "$TARGET"

launchctl bootout "gui/${UID_VALUE}" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID_VALUE}" "$TARGET"
launchctl enable "gui/${UID_VALUE}/${PLIST_NAME%.plist}"
launchctl kickstart -k "gui/${UID_VALUE}/${PLIST_NAME%.plist}" || true

echo "installed=${TARGET}"
