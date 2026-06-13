#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${FENGBIAO_GIT_REMOTE:-origin}"
BRANCH="${FENGBIAO_GIT_BRANCH:-main}"

cd "$ROOT"

send_bark_failure() {
  local body="$1"
  local endpoint="${BARK_URL:-}"
  local key="${BARK_KEY:-}"
  local server="${BARK_SERVER:-https://api.day.app}"

  if [[ -z "$endpoint" && -n "$key" ]]; then
    endpoint="${server%/}/${key}"
  fi

  if [[ -z "$endpoint" ]]; then
    echo "Bark push skipped: BARK_URL/BARK_KEY is not configured" >&2
    return 0
  fi

  python3 - "$endpoint" "$body" <<'PY' | curl -fsS -m 10 -X POST -H 'Content-Type: application/json' --data-binary @- "$endpoint" >/dev/null || true
import json
import sys

print(json.dumps({"title": "Codex 项目结论", "body": sys.argv[2]}, ensure_ascii=False))
PY
}

pull_rc=0
git fetch "$REMOTE" "$BRANCH" || pull_rc=$?
if [[ "$pull_rc" -eq 0 ]]; then
  git checkout "$BRANCH" || pull_rc=$?
fi
if [[ "$pull_rc" -eq 0 ]]; then
  git pull --ff-only "$REMOTE" "$BRANCH" || pull_rc=$?
fi
if [[ "$pull_rc" -ne 0 ]]; then
  echo "git refresh exited with ${pull_rc}; continuing with the current runtime clone" >&2
fi

bash ./scripts/publish_github_pages.sh --sync
publish_rc=$?

if [[ "$pull_rc" -ne 0 || "$publish_rc" -ne 0 ]]; then
  send_bark_failure "封标大师每日同步发布异常：git=${pull_rc}, publish=${publish_rc}；已尽量发布可用快照，需要小黑查看 ~/Library/Logs/fengbiao-pages-sync.err.log"
fi

if [[ "$publish_rc" -ne 0 ]]; then
  exit "$publish_rc"
fi

exit "$pull_rc"
