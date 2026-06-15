from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutomationScriptTests(unittest.TestCase):
    def test_publish_script_guards_candidate_snapshot_before_rewriting_pages_worktree(self):
        script = (ROOT / "scripts/publish_github_pages.sh").read_text(encoding="utf-8")

        guard_index = script.index("guard_public_snapshot")
        rewrite_index = script.index('find "$WORKTREE" -mindepth 1')

        self.assertLess(guard_index, rewrite_index)
        self.assertIn("${REMOTE}/${PAGES_BRANCH}:fengbiao-snapshot.json", script)

    def test_run_job_syncs_canonical_data_before_daily_publish(self):
        script = (ROOT / "scripts/run_pages_sync_job.sh").read_text(encoding="utf-8")

        sync_index = script.index("sync_runtime_data")
        publish_index = script.index("publish_github_pages.sh --sync")

        self.assertLess(sync_index, publish_index)
        self.assertIn("FENGBIAO_CANONICAL_DATA_ROOT", script)


if __name__ == "__main__":
    unittest.main()
