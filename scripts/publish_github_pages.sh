#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REMOTE="${FENGBIAO_GIT_REMOTE:-origin}"
PAGES_BRANCH="${FENGBIAO_PAGES_BRANCH:-gh-pages}"
COVER_MAX_PX="${FENGBIAO_COVER_MAX_PX:-640}"
COVER_JPEG_QUALITY="${FENGBIAO_COVER_JPEG_QUALITY:-72}"
RUN_SYNC=0

usage() {
  printf 'Usage: %s [--sync]\n' "$(basename "$0")"
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
  PYTHONPATH=src "$PYTHON_BIN" -m fengbiao.cli daily-run
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
    git clone --depth 1 --branch "$PAGES_BRANCH" "$remote_url" "$WORKTREE"
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
  git -C "$WORKTREE" fetch "$REMOTE" "$PAGES_BRANCH" || true
  git -C "$WORKTREE" checkout "$PAGES_BRANCH"
  git -C "$WORKTREE" pull --ff-only "$REMOTE" "$PAGES_BRANCH" || true
fi

find "$WORKTREE" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "${DIST}/." "$WORKTREE/"
touch "${WORKTREE}/.nojekyll"

git -C "$WORKTREE" add -A
if git -C "$WORKTREE" diff --cached --quiet; then
  echo "gh-pages unchanged"
else
  git -C "$WORKTREE" commit -m "deploy: update fengbiao pages snapshot"
  git -C "$WORKTREE" push -u "$REMOTE" "$PAGES_BRANCH"
fi

echo "published_base=${PAGES_BASE}"
echo "published_branch=${PAGES_BRANCH}"
