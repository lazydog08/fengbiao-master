from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from fengbiao.db import Database
from fengbiao.ingest import backfill_all
from fengbiao.fetch.bilibili_space import BilibiliRiskControlError
from fengbiao.models import Creator, Video


def _minimal_png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )


class BackfillTests(unittest.TestCase):
    def test_backfill_uses_existing_db_path_and_is_idempotent(self):
        with TemporaryDirectory() as tmp_dir:
            creators_path = Path(tmp_dir) / "creators.json"
            settings_path = Path(tmp_dir) / "settings.json"
            creators_path.write_text(
                json.dumps(
                    {
                        "creators": [
                            {
                                "platform": "bilibili",
                                "name": "影视飓风",
                                "bili_mid": "946974",
                                "tags": ["科技"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "paths": {"db": f"{tmp_dir}/fengbiao.sqlite3", "covers": f"{tmp_dir}/covers", "logs": f"{tmp_dir}/logs"},
                        "http": {"min_interval_sec": 0, "timeout_sec": 3, "max_retries": 0},
                        "backfill": {"bili_page_interval_sec": 0, "bili_page_size": 30, "years": 3},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            creator = Creator(platform="bilibili", name="影视飓风", creator_key="946974")
            videos = [
                Video(
                    platform="bilibili",
                    platform_video_id="BV1",
                    creator_key="946974",
                    title="标题",
                    url="https://www.bilibili.com/video/BV1",
                    cover_url="",
                    published_at="2026-06-01T00:00:00+00:00",
                    play_count=10,
                )
            ]

            with patch("fengbiao.ingest.fetch_space_archives", return_value=(creator, videos, "source")):
                first = backfill_all(creators_path, settings_path, years=3, platform="bilibili", cache_covers=False)
                second = backfill_all(creators_path, settings_path, years=3, platform="bilibili", cache_covers=False)

            self.assertEqual(first["videos_seen"], 1)
            self.assertEqual(first["new_videos"], 1)
            self.assertEqual(second["videos_seen"], 1)
            self.assertEqual(second["new_videos"], 0)
            self.assertEqual(first["creators_checked"], 1)
            self.assertEqual(first["errors"], [])

    def test_bilibili_backfill_falls_back_to_ytdlp_when_space_is_rate_limited(self):
        with TemporaryDirectory() as tmp_dir:
            creators_path = Path(tmp_dir) / "creators.json"
            settings_path = Path(tmp_dir) / "settings.json"
            creators_path.write_text(
                json.dumps(
                    {
                        "creators": [
                            {
                                "platform": "bilibili",
                                "name": "先看评测",
                                "bili_mid": "483311105",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "paths": {"db": f"{tmp_dir}/fengbiao.sqlite3", "covers": f"{tmp_dir}/covers", "logs": f"{tmp_dir}/logs"},
                        "http": {"min_interval_sec": 0, "timeout_sec": 3, "max_retries": 0},
                        "backfill": {"bili_page_interval_sec": 0, "bili_page_size": 30, "years": 3, "bili_ytdlp_fallback": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            creator = Creator(platform="bilibili", name="先看评测", creator_key="483311105")
            videos = [
                Video(
                    platform="bilibili",
                    platform_video_id="BV1",
                    creator_key="483311105",
                    title="标题",
                    url="https://www.bilibili.com/video/BV1",
                    cover_url="",
                    play_count=10,
                )
            ]

            with patch("fengbiao.ingest.fetch_space_archives", side_effect=BilibiliRiskControlError("412")), patch(
                "fengbiao.ingest.fetch_space_archives_via_ytdlp", return_value=(creator, videos, "fallback-source")
            ) as fallback:
                summary = backfill_all(creators_path, settings_path, years=3, platform="bilibili", cache_covers=False)

            fallback.assert_called_once()
            self.assertEqual(summary["videos_seen"], 1)
            self.assertEqual(summary["errors"], [])

    def test_backfill_skips_rejected_cover_dimensions_after_cache(self):
        with TemporaryDirectory() as tmp_dir:
            creators_path = Path(tmp_dir) / "creators.json"
            settings_path = Path(tmp_dir) / "settings.json"
            db_path = Path(tmp_dir) / "fengbiao.sqlite3"
            cover_path = Path(tmp_dir) / "short-wrapper.png"
            cover_path.write_bytes(_minimal_png_header(480, 360))
            creators_path.write_text(
                json.dumps(
                    {
                        "creators": [
                            {
                                "platform": "bilibili",
                                "name": "影视飓风",
                                "bili_mid": "946974",
                                "tags": ["科技"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                json.dumps(
                    {
                        "paths": {"db": str(db_path), "covers": f"{tmp_dir}/covers", "logs": f"{tmp_dir}/logs"},
                        "http": {"min_interval_sec": 0, "timeout_sec": 3, "max_retries": 0},
                        "backfill": {"bili_page_interval_sec": 0, "bili_page_size": 30, "years": 3},
                        "cover_filters": {"reject_dimensions": [[480, 360]]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            creator = Creator(platform="bilibili", name="影视飓风", creator_key="946974")
            videos = [
                Video(
                    platform="bilibili",
                    platform_video_id="BVSHORT",
                    creator_key="946974",
                    title="短视频外壳图",
                    url="https://www.bilibili.com/video/BVSHORT",
                    cover_url="https://example.com/short.png",
                    play_count=10,
                )
            ]

            with patch("fengbiao.ingest.fetch_space_archives", return_value=(creator, videos, "source")), patch(
                "fengbiao.ingest.cache_cover", return_value=(str(cover_path), "sha-short")
            ):
                summary = backfill_all(creators_path, settings_path, years=3, platform="bilibili", cache_covers=True)

            db = Database(db_path)
            self.assertEqual(summary["videos_seen"], 0)
            self.assertEqual(summary["new_videos"], 0)
            self.assertEqual(db.count("videos"), 0)
            self.assertEqual(summary["skipped"][0]["reason"], "rejected_cover_dimensions")
