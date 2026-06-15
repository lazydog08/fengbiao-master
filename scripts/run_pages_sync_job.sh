#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REMOTE="${FENGBIAO_GIT_REMOTE:-origin}"
BRANCH="${FENGBIAO_GIT_BRANCH:-main}"
CANONICAL_DATA_ROOT="${FENGBIAO_CANONICAL_DATA_ROOT:-}"
GIT_RETRY_ATTEMPTS="${FENGBIAO_GIT_RETRY_ATTEMPTS:-3}"
GIT_RETRY_SLEEP_SEC="${FENGBIAO_GIT_RETRY_SLEEP_SEC:-5}"
REQUIRE_GIT_REFRESH="${FENGBIAO_REQUIRE_GIT_REFRESH:-1}"

cd "$ROOT"

send_bark_failure() {
  local body="$1"
  local codex_bark="/Users/lazydog/.codex/bin/codex-bark"
  local endpoint="${BARK_URL:-}"
  local key="${BARK_KEY:-}"
  local server="${BARK_SERVER:-https://api.day.app}"

  if [[ -x "$codex_bark" ]]; then
    "$codex_bark" "Codex 项目结论" "$body" >/dev/null || echo "Bark push failed via codex-bark" >&2
    return 0
  fi

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

git_retry() {
  local attempt=1
  local rc=0
  while true; do
    "$@"
    rc=$?
    if [[ "$rc" -eq 0 || "$attempt" -ge "$GIT_RETRY_ATTEMPTS" ]]; then
      return "$rc"
    fi
    echo "git command failed with ${rc}; retry ${attempt}/${GIT_RETRY_ATTEMPTS}: $*" >&2
    sleep "$GIT_RETRY_SLEEP_SEC"
    attempt=$((attempt + 1))
  done
}

sync_canonical_data() {
  if [[ -z "$CANONICAL_DATA_ROOT" || ! -d "$CANONICAL_DATA_ROOT/data" ]]; then
    return 0
  fi
  PYTHONPATH="${ROOT}/src" "$PYTHON_BIN" - "$CANONICAL_DATA_ROOT" "$ROOT" <<'PY'
import json
import sys

from fengbiao.runtime_data import sync_runtime_data

result = sync_runtime_data(sys.argv[1], sys.argv[2])
print(json.dumps({"runtimeDataSync": result}, ensure_ascii=False, sort_keys=True))
PY
}

pull_rc=0
git_retry git fetch "$REMOTE" "$BRANCH" || pull_rc=$?
if [[ "$pull_rc" -eq 0 ]]; then
  git checkout "$BRANCH" || pull_rc=$?
fi
if [[ "$pull_rc" -eq 0 ]]; then
  git_retry git pull --ff-only "$REMOTE" "$BRANCH" || pull_rc=$?
fi
if [[ "$pull_rc" -ne 0 ]]; then
  if [[ "$REQUIRE_GIT_REFRESH" == "1" ]]; then
    echo "git refresh exited with ${pull_rc}; stopping before publish" >&2
    send_bark_failure "封标大师每日同步发布异常：git=${pull_rc}，已停止发布以避免旧运行副本覆盖线上；需要修复网络或认证后重跑。"
    exit "$pull_rc"
  fi
  echo "git refresh exited with ${pull_rc}; continuing because FENGBIAO_REQUIRE_GIT_REFRESH=${REQUIRE_GIT_REFRESH}" >&2
fi

sync_rc=0
sync_canonical_data || sync_rc=$?
if [[ "$sync_rc" -ne 0 ]]; then
  echo "canonical runtime data sync exited with ${sync_rc}; stopping before publish" >&2
  send_bark_failure "封标大师每日同步发布异常：运行副本数据同步失败 sync=${sync_rc}；已停止发布以避免旧快照覆盖线上。"
  exit "$sync_rc"
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
