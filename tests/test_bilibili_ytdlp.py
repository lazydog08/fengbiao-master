from datetime import datetime, timezone
import subprocess
import unittest
from unittest.mock import Mock, patch

from fengbiao.fetch.bilibili_ytdlp import (
    fetch_space_archives_via_ytdlp,
    parse_flat_entries,
    parse_view_detail,
)


class BilibiliYtDlpTests(unittest.TestCase):
    def test_parse_flat_entries_deduplicates_bvids(self):
        entries = parse_flat_entries(
            [
                '{"id":"BV1","url":"https://www.bilibili.com/video/BV1"}',
                '{"id":"BV2"}',
                '{"id":"BV1"}',
                'not-json',
                '{"id":"av123"}',
            ]
        )

        self.assertEqual(entries, ["BV1", "BV2"])

    def test_parse_view_detail_maps_recent_video(self):
        payload = {
            "code": 0,
            "data": {
                "bvid": "BV1",
                "title": "标题",
                "pic": "http://i0.hdslb.com/bfs/archive/a.jpg",
                "pubdate": 1781254800,
                "stat": {"view": 100, "like": 9, "coin": 3, "favorite": 8, "danmaku": 2},
            },
        }

        video, is_old = parse_view_detail(payload, creator_key="946974", cutoff=datetime(2023, 6, 13, tzinfo=timezone.utc))

        self.assertFalse(is_old)
        self.assertEqual(video.platform_video_id, "BV1")
        self.assertEqual(video.title, "标题")
        self.assertEqual(video.cover_url, "https://i0.hdslb.com/bfs/archive/a.jpg")
        self.assertEqual(video.play_count, 100)
        self.assertEqual(video.like_count, 9)
        self.assertEqual(video.coin_count, 3)
        self.assertEqual(video.favorite_count, 8)
        self.assertEqual(video.danmaku_count, 2)

    def test_fetch_space_archives_via_ytdlp_uses_flat_playlist_without_cookies(self):
        completed = subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=0,
            stdout='{"id":"BV1"}\n',
            stderr="",
        )
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 0,
            "data": {
                "bvid": "BV1",
                "title": "标题",
                "pic": "http://i0.hdslb.com/bfs/archive/a.jpg",
                "pubdate": 1781254800,
                "stat": {"view": 100},
            },
        }
        response.raise_for_status.return_value = None

        with patch("fengbiao.fetch.bilibili_ytdlp.shutil.which", return_value="/usr/local/bin/yt-dlp"), patch(
            "fengbiao.fetch.bilibili_ytdlp.subprocess.run", return_value=completed
        ) as run, patch("fengbiao.fetch.bilibili_ytdlp.requests.Session") as session_cls:
            session_cls.return_value.get.return_value = response
            creator, videos, source_url = fetch_space_archives_via_ytdlp(
                "影视飓风",
                "946974",
                "UA",
                3,
                datetime(2023, 6, 13, tzinfo=timezone.utc),
                ytdlp_path="yt-dlp",
                ytdlp_timeout=60,
                playlist_end=1200,
                detail_interval_sec=0,
            )

        command = run.call_args.args[0]
        self.assertIn("--flat-playlist", command)
        self.assertIn("--playlist-end", command)
        self.assertNotIn("--cookies", command)
        self.assertNotIn("--cookies-from-browser", command)
        self.assertEqual(creator.creator_key, "946974")
        self.assertEqual(len(videos), 1)
        self.assertEqual(source_url, "https://space.bilibili.com/946974/video")

    def test_fetch_space_archives_via_ytdlp_skips_missing_details(self):
        completed = subprocess.CompletedProcess(
            args=["yt-dlp"],
            returncode=0,
            stdout='{"id":"BV404"}\n{"id":"BVOK"}\n',
            stderr="",
        )
        missing = Mock()
        missing.status_code = 200
        missing.json.return_value = {"code": -404, "message": "啥都木有"}
        missing.raise_for_status.return_value = None
        ok = Mock()
        ok.status_code = 200
        ok.json.return_value = {
            "code": 0,
            "data": {
                "bvid": "BVOK",
                "title": "标题",
                "pic": "http://i0.hdslb.com/bfs/archive/a.jpg",
                "pubdate": 1781254800,
                "stat": {"view": 100},
            },
        }
        ok.raise_for_status.return_value = None

        with patch("fengbiao.fetch.bilibili_ytdlp.shutil.which", return_value="/usr/local/bin/yt-dlp"), patch(
            "fengbiao.fetch.bilibili_ytdlp.subprocess.run", return_value=completed
        ), patch("fengbiao.fetch.bilibili_ytdlp.requests.Session") as session_cls:
            session_cls.return_value.get.side_effect = [missing, ok]
            _, videos, _ = fetch_space_archives_via_ytdlp(
                "影视飓风",
                "946974",
                "UA",
                3,
                datetime(2023, 6, 13, tzinfo=timezone.utc),
                detail_interval_sec=0,
            )

        self.assertEqual([video.platform_video_id for video in videos], ["BVOK"])


if __name__ == "__main__":
    unittest.main()
