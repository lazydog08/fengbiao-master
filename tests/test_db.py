import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fengbiao.db import Database
from fengbiao.models import Creator, Video


class DatabaseTests(unittest.TestCase):
    def test_init_adds_sample_card_analysis_column_idempotently(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")

            db.init()
            db.init()

            with db.connect() as conn:
                columns = [row["name"] for row in conn.execute("PRAGMA table_info(sample_cards)").fetchall()]

            self.assertEqual(columns.count("analysis_json"), 1)

    def test_database_ingest_is_idempotent_and_appends_snapshots(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="影视飓风", creator_key="946974", follower_count=100)
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="946974",
                title="标题A",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                published_at="2026-06-01T00:00:00+00:00",
                play_count=100,
            )

            db.upsert_creator(creator)
            first = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            second = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T02:00:00+00:00")

            self.assertEqual(first, second)
            self.assertEqual(db.count("videos"), 1)
            self.assertEqual(db.count("video_snapshots"), 2)

    def test_foreign_keys_are_enforced_on_new_connections(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()

            with db.connect() as conn:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO videos(creator_id, platform, platform_video_id, url, title, first_seen_at, last_seen_at)
                        VALUES(999, 'bilibili', 'BV404', 'https://example.com', 'bad', 't1', 't1')
                        """
                    )

    def test_cover_change_is_logged_when_attached_cover_changes(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="影视飓风", creator_key="946974", follower_count=100)
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="946974",
                title="标题A",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=100,
            )

            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            first_cover = db.upsert_cover(video_id, "https://example.com/a.jpg", "a.jpg", "sha-a", "2026-06-01T01:00:01+00:00")
            db.attach_cover(video_id, first_cover, "2026-06-01T01:00:01+00:00")
            second_cover = db.upsert_cover(video_id, "https://example.com/b.jpg", "b.jpg", "sha-b", "2026-06-01T02:00:01+00:00")
            db.attach_cover(video_id, second_cover, "2026-06-01T02:00:01+00:00")

            with db.connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS c FROM change_log WHERE field='cover'").fetchone()
                self.assertEqual(row["c"], 1)

    def test_same_cover_hash_can_belong_to_different_videos(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="影视飓风", creator_key="946974", follower_count=100)
            db.upsert_creator(creator)
            video_a = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="946974",
                title="标题A",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
            )
            video_b = Video(
                platform="bilibili",
                platform_video_id="BV2",
                creator_key="946974",
                title="标题B",
                url="https://www.bilibili.com/video/BV2",
                cover_url="https://example.com/b.jpg",
            )

            video_a_id = db.upsert_video_with_snapshot(creator, video_a, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            video_b_id = db.upsert_video_with_snapshot(creator, video_b, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            cover_a_id = db.upsert_cover(video_a_id, video_a.cover_url, "a.jpg", "same-sha", "2026-06-01T01:00:01+00:00")
            cover_b_id = db.upsert_cover(video_b_id, video_b.cover_url, "b.jpg", "same-sha", "2026-06-01T01:00:01+00:00")

            self.assertNotEqual(cover_a_id, cover_b_id)

    def test_upsert_creator_preserves_existing_follower_count_when_missing(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            db.upsert_creator(Creator(platform="bilibili", name="影视飓风", creator_key="946974", follower_count=1000))
            db.upsert_creator(Creator(platform="bilibili", name="影视飓风", creator_key="946974", follower_count=None))

            with db.connect() as conn:
                row = conn.execute(
                    "SELECT follower_count FROM creators WHERE platform='bilibili' AND creator_key='946974'"
                ).fetchone()

            self.assertEqual(row["follower_count"], 1000)

    def test_delete_videos_cascade_removes_dependent_rows(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="youtube", name="Linus Tech Tips", creator_key="CHANNEL")
            video = Video(
                platform="youtube",
                platform_video_id="short1",
                creator_key="CHANNEL",
                title="Short",
                url="https://www.youtube.com/watch?v=short1",
                cover_url="https://example.com/short.jpg",
            )
            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            cover_id = db.upsert_cover(video_id, video.cover_url, "short.jpg", "sha-short", "2026-06-01T01:00:01+00:00")
            db.attach_cover(video_id, cover_id, "2026-06-01T01:00:01+00:00")

            deleted = db.delete_videos_cascade([video_id])

            self.assertEqual(deleted, 1)
            self.assertEqual(db.count("videos"), 0)
            self.assertEqual(db.count("video_snapshots"), 0)
            self.assertEqual(db.count("cover_assets"), 0)
            self.assertEqual(db.count("sample_cards"), 0)
            with db.connect() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_refresh_metrics_populates_rule_analysis_json(self):
        with TemporaryDirectory() as tmp_dir:
            cover_path = Path(tmp_dir) / "cover.png"
            cover_path.write_bytes(_minimal_png_header(1280, 720))
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="懒狗小黑", creator_key="516185777", follower_count=1000)
            high_video = Video(
                platform="bilibili",
                platform_video_id="BVHIGH",
                creator_key="516185777",
                title="智能眼镜 VS 手机？我戴了7天后发现真相",
                url="https://www.bilibili.com/video/BVHIGH",
                cover_url="https://example.com/high.jpg",
                play_count=300,
            )
            low_video = Video(
                platform="bilibili",
                platform_video_id="BVLOW",
                creator_key="516185777",
                title="普通桌面整理",
                url="https://www.bilibili.com/video/BVLOW",
                cover_url="https://example.com/low.jpg",
                play_count=100,
            )

            db.upsert_creator(creator)
            high_id = db.upsert_video_with_snapshot(creator, high_video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            low_id = db.upsert_video_with_snapshot(creator, low_video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            cover_id = db.upsert_cover(high_id, high_video.cover_url, str(cover_path), "sha-high", "2026-06-01T01:00:01+00:00")
            db.attach_cover(high_id, cover_id, "2026-06-01T01:00:01+00:00")
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO change_log(video_id, field, changed_at, old_value, new_value) VALUES(?, 'title', ?, ?, ?)",
                    (high_id, "2026-06-01T02:00:00+00:00", "旧标题", high_video.title),
                )

            db.refresh_metrics()

            with db.connect() as conn:
                row = conn.execute("SELECT metrics_json, analysis_json FROM sample_cards WHERE video_id=?", (high_id,)).fetchone()
                low_row = conn.execute("SELECT analysis_json FROM sample_cards WHERE video_id=?", (low_id,)).fetchone()

            metrics = json.loads(row["metrics_json"])
            analysis = json.loads(row["analysis_json"])
            low_analysis = json.loads(low_row["analysis_json"])
            self.assertEqual(metrics["relative_to_baseline"], 1.5)
            self.assertEqual(analysis["performance"]["bucket"], "high")
            self.assertEqual(analysis["cover"]["width"], 1280)
            self.assertTrue(analysis["cover"]["title_changed"])
            self.assertEqual(low_analysis["performance"]["bucket"], "low")

    def test_refresh_metrics_preserves_previous_metrics_when_latest_play_count_is_missing(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="懒狗小黑", creator_key="516185777", follower_count=1000)
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="516185777",
                title="智能眼镜这次能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=300,
            )
            baseline_video = Video(
                platform="bilibili",
                platform_video_id="BV2",
                creator_key="516185777",
                title="普通样本",
                url="https://www.bilibili.com/video/BV2",
                cover_url="https://example.com/b.jpg",
                play_count=100,
            )

            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            db.upsert_video_with_snapshot(creator, baseline_video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            db.refresh_metrics()
            with db.connect() as conn:
                previous = conn.execute("SELECT metrics_json FROM sample_cards WHERE video_id=?", (video_id,)).fetchone()["metrics_json"]

            missing_play_video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="516185777",
                title="智能眼镜这次能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=None,
            )
            db.upsert_video_with_snapshot(creator, missing_play_video, cover_id=None, fetched_at="2026-06-02T01:00:00+00:00")

            db.refresh_metrics()

            with db.connect() as conn:
                row = conn.execute("SELECT metrics_json, analysis_json FROM sample_cards WHERE video_id=?", (video_id,)).fetchone()

            analysis = json.loads(row["analysis_json"])
            self.assertEqual(json.loads(row["metrics_json"]), json.loads(previous))
            self.assertEqual(analysis["performance"]["bucket"], "high")

    def test_refresh_metrics_keeps_metrics_when_analysis_fails(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="懒狗小黑", creator_key="516185777", follower_count=1000)
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="516185777",
                title="智能眼镜这次能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=100,
            )

            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")

            with patch("fengbiao.db.analyze_sample", side_effect=RuntimeError("analysis down")):
                db.refresh_metrics()

            with db.connect() as conn:
                row = conn.execute("SELECT metrics_json, analysis_json FROM sample_cards WHERE video_id=?", (video_id,)).fetchone()

            self.assertIsNotNone(row["metrics_json"])
            self.assertIsNone(row["analysis_json"])

    def test_refresh_metrics_clears_stale_analysis_when_analysis_fails_after_metrics_change(self):
        with TemporaryDirectory() as tmp_dir:
            db = Database(f"{tmp_dir}/fengbiao.sqlite3")
            db.init()
            creator = Creator(platform="bilibili", name="懒狗小黑", creator_key="516185777", follower_count=1000)
            video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="516185777",
                title="智能眼镜这次能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=300,
            )
            baseline_video = Video(
                platform="bilibili",
                platform_video_id="BV2",
                creator_key="516185777",
                title="普通样本",
                url="https://www.bilibili.com/video/BV2",
                cover_url="https://example.com/b.jpg",
                play_count=100,
            )

            db.upsert_creator(creator)
            video_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            db.upsert_video_with_snapshot(creator, baseline_video, cover_id=None, fetched_at="2026-06-01T01:00:00+00:00")
            db.refresh_metrics()

            updated_video = Video(
                platform="bilibili",
                platform_video_id="BV1",
                creator_key="516185777",
                title="智能眼镜这次能当主力屏幕吗？",
                url="https://www.bilibili.com/video/BV1",
                cover_url="https://example.com/a.jpg",
                play_count=50,
            )
            db.upsert_video_with_snapshot(creator, updated_video, cover_id=None, fetched_at="2026-06-02T01:00:00+00:00")

            with patch("fengbiao.db.analyze_sample", side_effect=RuntimeError("analysis down")):
                db.refresh_metrics()

            with db.connect() as conn:
                row = conn.execute("SELECT metrics_json, analysis_json FROM sample_cards WHERE video_id=?", (video_id,)).fetchone()

            metrics = json.loads(row["metrics_json"])
            self.assertEqual(metrics["relative_to_baseline"], 0.6667)
            self.assertIsNone(row["analysis_json"])


def _minimal_png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + width.to_bytes(4, "big") + height.to_bytes(4, "big")
