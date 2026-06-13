import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fengbiao.db import Database
from fengbiao.models import Creator, Video


class DatabaseTests(unittest.TestCase):
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
