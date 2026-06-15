# Daily Automation Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the scheduled Fengbiao Pages job from publishing stale runtime data, and repair the live runtime copy so it uses the current T7 data source.

**Architecture:** Add a small snapshot regression guard that compares the candidate public snapshot against the last known published snapshot before `gh-pages` is changed. Harden the scheduled runtime scripts with bounded Git retries and an explicit canonical data sync from the T7 workspace into the runtime clone.

**Tech Stack:** Bash launch scripts, Python stdlib, SQLite project data, existing unittest suite.

---

### Task 1: Snapshot Regression Guard

**Files:**
- Create: `src/fengbiao/snapshot_guard.py`
- Test: `tests/test_snapshot_guard.py`
- Modify: `scripts/publish_github_pages.sh`

- [ ] Write failing tests for rejecting a candidate snapshot with fewer samples than the published baseline.
- [ ] Write failing tests for rejecting a candidate snapshot older than the published baseline.
- [ ] Implement metadata parsing and comparison in `src/fengbiao/snapshot_guard.py`.
- [ ] Wire the guard into `scripts/publish_github_pages.sh` before the Pages worktree is rewritten.
- [ ] Verify with `PYTHONPATH=src python3 -m unittest tests.test_snapshot_guard -v`.

### Task 2: Runtime Data Sync And Git Retry

**Files:**
- Modify: `scripts/run_pages_sync_job.sh`
- Modify: `scripts/install_pages_sync_launch_agent.sh`
- Modify: `ops/launchagents/com.lazydog.fengbiao-pages-sync.plist`

- [ ] Add bounded retry helpers for transient `git fetch`, `pull`, and `push` operations.
- [ ] Sync canonical data from `FENGBIAO_CANONICAL_DATA_ROOT` when its SQLite database is larger or newer than the runtime copy.
- [ ] Install the LaunchAgent with `FENGBIAO_CANONICAL_DATA_ROOT` pointing at the source workspace.
- [ ] Keep the runtime DB backed up before replacement.

### Task 3: Live Repair And Verification

**Files:**
- Runtime clone: `~/Library/Application Support/fengbiao-master-runtime`
- Pages worktree: `~/Library/Application Support/封标大师-gh-pages`

- [ ] Run focused unit tests and shell syntax checks.
- [ ] Install/update the runtime LaunchAgent from the T7 repo.
- [ ] Clear the stale local `gh-pages` ahead commit by resetting the generated Pages worktree to `origin/gh-pages`.
- [ ] Run the scheduled job once manually.
- [ ] Verify local runtime snapshot, raw GitHub snapshot, and LaunchAgent state.
