import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fengbiao.snapshot_guard import SnapshotRegressionError, guard_public_snapshot


class SnapshotGuardTests(unittest.TestCase):
    def test_rejects_candidate_with_fewer_samples_than_published_baseline(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            candidate = _write_snapshot(root / "candidate.json", samples=3894, generated_at="2026-06-15T02:38:18+00:00")
            baseline = _write_snapshot(root / "baseline.json", samples=3973, generated_at="2026-06-14T14:40:34+00:00")

            with self.assertRaisesRegex(SnapshotRegressionError, "fewer samples"):
                guard_public_snapshot(candidate, [baseline])

    def test_rejects_candidate_older_than_published_baseline(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            candidate = _write_snapshot(root / "candidate.json", samples=3973, generated_at="2026-06-14T10:00:00+00:00")
            baseline = _write_snapshot(root / "baseline.json", samples=3973, generated_at="2026-06-14T14:40:34+00:00")

            with self.assertRaisesRegex(SnapshotRegressionError, "older"):
                guard_public_snapshot(candidate, [baseline])

    def test_allows_equal_or_newer_candidate(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            candidate = _write_snapshot(root / "candidate.json", samples=3974, generated_at="2026-06-15T02:38:18+00:00")
            baseline = _write_snapshot(root / "baseline.json", samples=3973, generated_at="2026-06-14T14:40:34+00:00")

            metadata = guard_public_snapshot(candidate, [baseline])

        self.assertEqual(metadata.sample_count, 3974)


def _write_snapshot(path: Path, samples: int, generated_at: str) -> Path:
    payload = {
        "generatedAt": generated_at,
        "samples": [{"id": index} for index in range(samples)],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
