from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fengbiao.db import Database
from fengbiao.models import Creator, Video


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_frontend_snapshot.py"


def load_export_module():
    spec = importlib.util.spec_from_file_location("export_frontend_snapshot", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("export_frontend_snapshot.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrontendSnapshotExportTests(unittest.TestCase):
    def test_exports_samples_with_parsed_json_and_copied_cover(self):
        module = load_export_module()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db_path = root / "data" / "db" / "fengbiao.sqlite3"
            source_cover = root / "data" / "covers" / "bilibili" / "946974" / "BV1_test.jpg"
            source_cover.parent.mkdir(parents=True)
            source_cover.write_bytes(b"\xff\xd8\xff\xdbfake-jpeg")

            db = Database(db_path)
            db.init()
            creator = Creator(
                platform="bilibili",
                name="影视飓风",
                creator_key="946974",
                tags=["科技评测", "智能眼镜"],
                note="适合看高密度封面和标题节奏",
                follower_count=1000,
            )
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="946974",
                title="智能眼镜这次真能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/cover.jpg",
                published_at="2026-06-01T00:00:00+00:00",
                play_count=2500,
                like_count=200,
                coin_count=30,
                favorite_count=90,
                danmaku_count=12,
            )

            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(
                creator,
                video,
                cover_id=None,
                fetched_at="2026-06-02T00:00:00+00:00",
            )
            cover_id = db.upsert_cover(
                video_id,
                video.cover_url,
                "data/covers/bilibili/946974/BV1_test.jpg",
                "sha-cover",
                "2026-06-02T00:00:01+00:00",
            )
            db.attach_cover(video_id, cover_id, "2026-06-02T00:00:01+00:00")
            db.update_latest_snapshot_cover(video_id, cover_id)
            with db.connect() as conn:
                conn.execute(
                    """
                    UPDATE sample_cards
                    SET track=?, human_note=?, metrics_json=?
                    WHERE video_id=?
                    """,
                    (
                        "智能眼镜",
                        "标题把产品疑问翻成真实使用场景",
                        json.dumps(
                            {
                                "baseline_play_count": 1000,
                                "relative_to_baseline": 2.5,
                                "views_per_follower": 2.5,
                            }
                        ),
                        video_id,
                    ),
                )

            yt_creator = Creator(platform="youtube", name="MKBHD", creator_key="yt", tags=["tech"], note="")
            yt_video = Video(
                platform="youtube",
                platform_video_id="yt1",
                creator_key="yt",
                title="A clean hardware thumbnail",
                url="https://youtube.com/watch?v=yt1",
                cover_url="https://example.com/y.jpg",
                play_count=None,
            )
            db.upsert_creator(yt_creator)
            db.upsert_video_with_snapshot(yt_creator, yt_video, cover_id=None, fetched_at="2026-06-03T00:00:00+00:00")

            output_path = root / "apps" / "web" / "public" / "fengbiao-snapshot.json"
            public_covers_dir = root / "apps" / "web" / "public" / "covers"

            summary = module.export_snapshot(
                project_root=root,
                db_path=db_path,
                output_path=output_path,
                public_covers_dir=public_covers_dir,
                cover_max_px=0,
            )

            self.assertEqual(summary["samples"], 2)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["counts"]["samples"], 2)
            first = payload["samples"][0]
            self.assertEqual(first["creator"]["tags"], ["tech"])
            self.assertIsNone(first["metrics"]["playCount"])
            second = payload["samples"][1]
            self.assertEqual(second["creator"]["tags"], ["科技评测", "智能眼镜"])
            self.assertEqual(second["card"]["relativeToBaseline"], 2.5)
            self.assertEqual(second["cover"]["url"], f"/covers/{video_id}.jpg")
            self.assertTrue((public_covers_dir / f"{video_id}.jpg").exists())

    def test_exports_with_malformed_json_and_missing_cover(self):
        module = load_export_module()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            db_path = root / "data" / "db" / "fengbiao.sqlite3"
            db = Database(db_path)
            db.init()

            creator = Creator(
                platform="bilibili",
                name="懒狗小黑",
                creator_key="xiaohei",
                tags=["科技评测"],
                note="",
            )
            video = Video(
                platform="bilibili",
                platform_video_id="BV2",
                creator_key="xiaohei",
                title="没有封面也要能进快照",
                url="https://www.bilibili.com/video/BV2",
                cover_url="https://example.com/missing.jpg",
                play_count=100,
            )
            db.upsert_creator(creator)
            db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-04T00:00:00+00:00")
            with db.connect() as conn:
                conn.execute("UPDATE creators SET tags=? WHERE creator_key=?", ("not-json", "xiaohei"))
                conn.execute("UPDATE sample_cards SET metrics_json=?", ("{broken",))

            output_path = root / "apps" / "web" / "public" / "fengbiao-snapshot.json"
            public_covers_dir = root / "apps" / "web" / "public" / "covers"
            public_covers_dir.mkdir(parents=True)
            stale_cover = public_covers_dir / "stale.jpg"
            stale_cover.write_bytes(b"stale")

            summary = module.export_snapshot(
                project_root=root,
                db_path=db_path,
                output_path=output_path,
                public_covers_dir=public_covers_dir,
            )

            self.assertEqual(summary["samples"], 1)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            exported = payload["samples"][0]
            self.assertEqual(exported["creator"]["tags"], [])
            self.assertIsNone(exported["card"]["relativeToBaseline"])
            self.assertIsNone(exported["cover"]["url"])
            self.assertFalse(stale_cover.exists())


if __name__ == "__main__":
    unittest.main()
