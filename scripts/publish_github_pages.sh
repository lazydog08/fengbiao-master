#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REMOTE="${FENGBIAO_GIT_REMOTE:-origin}"
PAGES_BRANCH="${FENGBIAO_PAGES_BRANCH:-gh-pages}"
COVER_MAX_PX="${FENGBIAO_COVER_MAX_PX:-640}"
COVER_JPEG_QUALITY="${FENGBIAO_COVER_JPEG_QUALITY:-72}"
ALLOW_SNAPSHOT_REGRESSION="${FENGBIAO_ALLOW_SNAPSHOT_REGRESSION:-0}"
GIT_RETRY_ATTEMPTS="${FENGBIAO_GIT_RETRY_ATTEMPTS:-3}"
GIT_RETRY_SLEEP_SEC="${FENGBIAO_GIT_RETRY_SLEEP_SEC:-5}"
RUN_SYNC=0
SYNC_RC=0
export GIT_TERMINAL_PROMPT=0

usage() {
  printf 'Usage: %s [--sync]\n' "$(basename "$0")"
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

guard_public_snapshot() {
  local candidate="$1"
  shift
  if [[ "$ALLOW_SNAPSHOT_REGRESSION" == "1" ]]; then
    echo "snapshot regression guard bypassed by FENGBIAO_ALLOW_SNAPSHOT_REGRESSION=1" >&2
    return 0
  fi
  PYTHONPATH="${ROOT}/src" "$PYTHON_BIN" - "$candidate" "$@" <<'PY'
import sys

from fengbiao.snapshot_guard import SnapshotRegressionError, guard_public_snapshot

try:
    metadata = guard_public_snapshot(sys.argv[1], sys.argv[2:])
except SnapshotRegressionError as exc:
    print(f"snapshot regression guard failed: {exc}", file=sys.stderr)
    raise SystemExit(3)

print(f"snapshot guard ok: samples={metadata.sample_count}")
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sync)
      RUN_SYNC=1
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

cd "$ROOT"

remote_url="$(git remote get-url "$REMOTE")"
repo_name="$(basename "$remote_url")"
repo_name="${repo_name%.git}"
PAGES_BASE="${FENGBIAO_PAGES_BASE:-/${repo_name}/}"
WORKTREE="${FENGBIAO_PAGES_WORKTREE:-$(dirname "$ROOT")/封标大师-gh-pages}"
DIST="${ROOT}/apps/web/dist"

root_real="$(cd "$ROOT" && pwd -P)"
worktree_parent="$(dirname "$WORKTREE")"
mkdir -p "$worktree_parent"
worktree_real_parent="$(cd "$worktree_parent" && pwd -P)"
worktree_real="${worktree_real_parent}/$(basename "$WORKTREE")"

if [[ "$worktree_real" == "$root_real" || "$worktree_real" == "$root_real"/* ]]; then
  echo "Refusing to publish into the source repository: $WORKTREE" >&2
  exit 2
fi

if [[ "$RUN_SYNC" -eq 1 ]]; then
  set +e
  sync_output="$(PYTHONPATH=src "$PYTHON_BIN" -m fengbiao.cli daily-run 2>&1)"
  sync_rc=$?
  SYNC_RC="$sync_rc"
  set -e
  printf '%s\n' "$sync_output"
  if [[ "$sync_rc" -ne 0 ]]; then
    echo "daily-run exited with ${sync_rc}; continuing to export and publish the latest local database snapshot" >&2
  fi
fi

"$PYTHON_BIN" scripts/export_frontend_snapshot.py --cover-max-px "$COVER_MAX_PX" --cover-jpeg-quality "$COVER_JPEG_QUALITY"

(
  cd apps/web
  if [[ ! -d node_modules ]]; then
    npm ci
  fi
  VITE_BASE_PATH="$PAGES_BASE" npm run build
)

test -s "${DIST}/index.html"
test -s "${DIST}/fengbiao-snapshot.json"
test -d "${DIST}/covers"

if [[ ! -d "$WORKTREE/.git" ]]; then
  if git ls-remote --exit-code --heads "$REMOTE" "$PAGES_BRANCH" >/dev/null 2>&1; then
    git_retry git clone --depth 1 --branch "$PAGES_BRANCH" "$remote_url" "$WORKTREE"
  else
    mkdir -p "$WORKTREE"
    git -C "$WORKTREE" init
    git -C "$WORKTREE" checkout -b "$PAGES_BRANCH"
    git -C "$WORKTREE" remote add "$REMOTE" "$remote_url"
  fi
else
  if ! git -C "$WORKTREE" remote get-url "$REMOTE" >/dev/null 2>&1; then
    git -C "$WORKTREE" remote add "$REMOTE" "$remote_url"
  fi
  git_retry git -C "$WORKTREE" fetch "$REMOTE" "$PAGES_BRANCH" || true
  git -C "$WORKTREE" checkout "$PAGES_BRANCH"
  if git -C "$WORKTREE" rev-parse --verify "${REMOTE}/${PAGES_BRANCH}" >/dev/null 2>&1; then
    git -C "$WORKTREE" reset --hard "${REMOTE}/${PAGES_BRANCH}"
  else
    git_retry git -C "$WORKTREE" pull --ff-only "$REMOTE" "$PAGES_BRANCH" || true
  fi
fi

BASELINE_DIR="$(mktemp -d)"
trap 'rm -rf "$BASELINE_DIR"' EXIT
BASELINE_FILES=()
if git -C "$WORKTREE" show "${REMOTE}/${PAGES_BRANCH}:fengbiao-snapshot.json" > "${BASELINE_DIR}/remote-snapshot.json" 2>/dev/null; then
  BASELINE_FILES+=("${BASELINE_DIR}/remote-snapshot.json")
fi
if [[ -f "${WORKTREE}/fengbiao-snapshot.json" ]]; then
  BASELINE_FILES+=("${WORKTREE}/fengbiao-snapshot.json")
fi
guard_public_snapshot "${DIST}/fengbiao-snapshot.json" "${BASELINE_FILES[@]}"

find "$WORKTREE" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "${DIST}/." "$WORKTREE/"
touch "${WORKTREE}/.nojekyll"

git -C "$WORKTREE" add -A
if git -C "$WORKTREE" diff --cached --quiet; then
  echo "gh-pages unchanged"
else
  git -C "$WORKTREE" commit -m "deploy: update fengbiao pages snapshot"
  git_retry git -C "$WORKTREE" push -u "$REMOTE" "$PAGES_BRANCH"
fi

echo "published_base=${PAGES_BASE}"
echo "published_branch=${PAGES_BRANCH}"
exit "$SYNC_RC"
