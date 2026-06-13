from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from fengbiao.db import Database
from fengbiao.models import Creator, Video
from fengbiao.sync_server import SyncService, make_handler


class SyncServerTests(unittest.TestCase):
    def test_get_snapshot_exports_db_payload_via_http(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_database(root)
            service = SyncService(project_root=root)

            with _running_server(service) as base_url:
                with urlopen(f"{base_url}/api/snapshot", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["counts"]["samples"], 1)
            self.assertEqual(payload["samples"][0]["title"], "同步入口测试样本")
            self.assertTrue((root / "apps" / "web" / "public" / "fengbiao-snapshot.json").exists())

    def test_get_snapshot_reuses_existing_snapshot_without_export(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            snapshot_path = root / "apps" / "web" / "public" / "fengbiao-snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            snapshot_path.write_text(
                json.dumps({"generatedAt": "cached", "counts": {"creators": 0, "videos": 0, "samples": 0}, "samples": []}),
                encoding="utf-8",
            )

            def fail_export(**_kwargs):
                raise AssertionError("existing snapshot should be reused")

            service = SyncService(project_root=root, export_func=fail_export)

            with _running_server(service) as base_url:
                with urlopen(f"{base_url}/api/snapshot", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["generatedAt"], "cached")

    def test_post_sync_runs_ingest_then_exports_snapshot(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_database(root)
            calls = []

            def fake_ingest(creators_path, settings_path, mode, cache_covers):
                calls.append(
                    {
                        "creators_path": str(creators_path),
                        "settings_path": str(settings_path),
                        "mode": mode,
                        "cache_covers": cache_covers,
                    }
                )
                return {
                    "mode": mode,
                    "creators_checked": 1,
                    "videos_seen": 1,
                    "new_videos": 0,
                    "covers_cached": 0,
                    "errors": [],
                }

            service = SyncService(project_root=root, ingest_func=fake_ingest)

            with _running_server(service) as base_url:
                request = Request(f"{base_url}/api/sync", method="POST")
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(calls[0]["mode"], "daily")
            self.assertTrue(calls[0]["cache_covers"])
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["ingest"]["creators_checked"], 1)
            self.assertEqual(payload["export"]["samples"], 1)
            self.assertEqual(payload["snapshot"]["counts"]["samples"], 1)

    def test_missing_database_returns_json_error(self):
        with TemporaryDirectory() as tmp_dir:
            service = SyncService(project_root=Path(tmp_dir))

            with _running_server(service) as base_url:
                with self.assertRaises(HTTPError) as raised:
                    urlopen(f"{base_url}/api/snapshot?export=1", timeout=5)

            error = raised.exception
            payload = json.loads(error.read().decode("utf-8"))
            self.assertEqual(error.code, 404)
            self.assertEqual(error.headers["Content-Type"], "application/json; charset=utf-8")
            self.assertIn("SQLite database not found", payload["error"])


class _running_server:
    def __init__(self, service: SyncService):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _seed_database(root: Path) -> None:
    db_path = root / "data" / "db" / "fengbiao.sqlite3"
    db = Database(db_path)
    db.init()
    creator = Creator(platform="bilibili", name="懒狗小黑", creator_key="xiaohei", tags=["科技评测"])
    video = Video(
        platform="bilibili",
        platform_video_id="BV-sync",
        creator_key="xiaohei",
        title="同步入口测试样本",
        url="https://www.bilibili.com/video/BV-sync",
        cover_url="https://example.com/cover.jpg",
        published_at="2026-06-13T00:00:00+00:00",
        play_count=1000,
    )
    db.upsert_creator(creator)
    db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-13T01:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
