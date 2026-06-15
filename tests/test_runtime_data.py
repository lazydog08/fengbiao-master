from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fengbiao.runtime_data import sync_runtime_data


class RuntimeDataTests(unittest.TestCase):
    def test_copies_canonical_database_when_it_has_more_data(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            canonical = root / "canonical"
            runtime = root / "runtime"
            _write_db(canonical / "data/db/fengbiao.sqlite3", creators=2, videos=3)
            _write_db(runtime / "data/db/fengbiao.sqlite3", creators=1, videos=1)
            source_cover = canonical / "data/covers/bilibili/123/BVTEST.jpg"
            source_cover.parent.mkdir(parents=True)
            source_cover.write_bytes(b"cover")

            result = sync_runtime_data(canonical, runtime, backup_suffix="test")

            self.assertTrue(result["dbCopied"])
            self.assertEqual(_count(runtime / "data/db/fengbiao.sqlite3", "creators"), 2)
            self.assertEqual(_count(runtime / "data/db/fengbiao.sqlite3", "videos"), 3)
            self.assertTrue((runtime / "data/db/fengbiao.sqlite3.backup.test").exists())
            self.assertEqual((runtime / "data/covers/bilibili/123/BVTEST.jpg").read_bytes(), b"cover")

    def test_removes_stale_runtime_sqlite_sidecar_files_when_copying_database(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            canonical = root / "canonical"
            runtime = root / "runtime"
            target_db = runtime / "data/db/fengbiao.sqlite3"
            _write_db(canonical / "data/db/fengbiao.sqlite3", creators=2, videos=3)
            _write_db(target_db, creators=1, videos=1)
            target_db.with_name("fengbiao.sqlite3-wal").write_bytes(b"stale")
            target_db.with_name("fengbiao.sqlite3-shm").write_bytes(b"stale")

            sync_runtime_data(canonical, runtime, backup_suffix="test")

            self.assertFalse(target_db.with_name("fengbiao.sqlite3-wal").exists())
            self.assertFalse(target_db.with_name("fengbiao.sqlite3-shm").exists())

    def test_does_not_overwrite_runtime_database_when_runtime_has_more_videos(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            canonical = root / "canonical"
            runtime = root / "runtime"
            _write_db(canonical / "data/db/fengbiao.sqlite3", creators=2, videos=3)
            _write_db(runtime / "data/db/fengbiao.sqlite3", creators=2, videos=4)

            result = sync_runtime_data(canonical, runtime, backup_suffix="test")

            self.assertFalse(result["dbCopied"])
            self.assertEqual(_count(runtime / "data/db/fengbiao.sqlite3", "videos"), 4)

    def test_force_overwrites_runtime_database_even_when_runtime_has_more_videos(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            canonical = root / "canonical"
            runtime = root / "runtime"
            _write_db(canonical / "data/db/fengbiao.sqlite3", creators=2, videos=3)
            _write_db(runtime / "data/db/fengbiao.sqlite3", creators=2, videos=4)

            result = sync_runtime_data(canonical, runtime, backup_suffix="test", force=True)

            self.assertTrue(result["dbCopied"])
            self.assertEqual(_count(runtime / "data/db/fengbiao.sqlite3", "videos"), 3)


def _write_db(path: Path, creators: int, videos: int) -> None:
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE creators(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE videos(id INTEGER PRIMARY KEY, title TEXT)")
        for index in range(creators):
            conn.execute("INSERT INTO creators(name) VALUES (?)", (f"creator-{index}",))
        for index in range(videos):
            conn.execute("INSERT INTO videos(title) VALUES (?)", (f"video-{index}",))


def _count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


if __name__ == "__main__":
    unittest.main()
