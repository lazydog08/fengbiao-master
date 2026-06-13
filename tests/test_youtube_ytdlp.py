from datetime import datetime, timezone
import subprocess
import unittest
from unittest.mock import Mock, patch

from fengbiao.fetch.youtube_ytdlp import (
    fetch_channel_videos,
    parse_flat_playlist,
    parse_watch_player_response,
    parse_ytdlp_lines,
)


class YouTubeYtDlpTests(unittest.TestCase):
    def test_parse_ytdlp_lines_maps_recent_videos_and_skips_old_or_bad_lines(self):
        lines = [
            '{"id":"new1","title":"New Video","webpage_url":"https://youtube.com/watch?v=new1","upload_date":"20260609","view_count":123,"thumbnails":[{"url":"https://thumb/small.jpg"},{"url":"https://thumb/big.jpg"}]}',
            "not json",
            '{"id":"old1","title":"Old Video","upload_date":"20200101","view_count":5}',
        ]
        cutoff = datetime(2023, 6, 13, tzinfo=timezone.utc)

        videos = parse_ytdlp_lines(lines, channel_id="CHANNEL", cutoff=cutoff)

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].platform, "youtube")
        self.assertEqual(videos[0].platform_video_id, "new1")
        self.assertEqual(videos[0].cover_url, "https://thumb/big.jpg")
        self.assertEqual(videos[0].published_at, "2026-06-09T00:00:00+00:00")
        self.assertEqual(videos[0].play_count, 123)

    def test_fetch_channel_videos_returns_skip_when_ytdlp_missing(self):
        with patch("fengbiao.fetch.youtube_ytdlp.shutil.which", return_value=None):
            videos, skipped = fetch_channel_videos("Name", "CHANNEL", datetime(2023, 6, 13, tzinfo=timezone.utc), ytdlp_path="yt-dlp")

        self.assertEqual(videos, [])
        self.assertEqual(skipped, "yt-dlp not found")

    def test_parse_flat_playlist_deduplicates_entries(self):
        entries = parse_flat_playlist({"entries": [{"id": "a"}, {"id": "b"}, {"id": "a"}, {}, None]})

        self.assertEqual([entry["id"] for entry in entries], ["a", "b"])

    def test_parse_watch_player_response_maps_public_metadata(self):
        payload = {
            "videoDetails": {
                "videoId": "new1",
                "title": "New Video",
                "viewCount": "12345",
                "thumbnail": {"thumbnails": [{"url": "https://thumb/small.jpg"}, {"url": "https://thumb/max.jpg"}]},
            },
            "microformat": {"playerMicroformatRenderer": {"publishDate": "2026-06-09T00:00:00Z"}},
        }

        video = parse_watch_player_response(payload, "CHANNEL")

        self.assertEqual(video.platform_video_id, "new1")
        self.assertEqual(video.title, "New Video")
        self.assertEqual(video.cover_url, "https://thumb/max.jpg")
        self.assertEqual(video.published_at, "2026-06-09T00:00:00+00:00")
        self.assertEqual(video.play_count, 12345)

    def test_parse_watch_player_response_skips_shorts_when_landscape_only(self):
        payload = {
            "videoDetails": {
                "videoId": "short1",
                "title": "Vertical short with 16x9 wrapper",
                "viewCount": "10",
                "thumbnail": {"thumbnails": [{"url": "https://thumb/max.jpg", "width": 1920, "height": 1080}]},
            },
            "microformat": {"playerMicroformatRenderer": {"publishDate": "2026-06-09", "isShortsEligible": True}},
        }

        video = parse_watch_player_response(payload, "CHANNEL", landscape_only=True)

        self.assertIsNone(video)

    def test_fetch_channel_videos_keeps_scanning_until_landscape_recent_limit(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"entries":[{"id":"short1","title":"Short"},{"id":"long1","title":"Long"}]}',
            stderr="",
        )
        cutoff = datetime(2023, 6, 13, tzinfo=timezone.utc)
        short_response = Mock()
        short_response.raise_for_status.return_value = None
        short_response.text = (
            '<script>var ytInitialPlayerResponse = '
            '{"videoDetails":{"videoId":"short1","title":"Short","viewCount":"10","thumbnail":{"thumbnails":[{"url":"https://thumb/short.jpg","width":1920,"height":1080}]}},'
            '"microformat":{"playerMicroformatRenderer":{"publishDate":"2026-06-09","isShortsEligible":true}}};</script>'
        )
        long_response = Mock()
        long_response.raise_for_status.return_value = None
        long_response.text = (
            '<script>var ytInitialPlayerResponse = '
            '{"videoDetails":{"videoId":"long1","title":"Long","viewCount":"123","thumbnail":{"thumbnails":[{"url":"https://thumb/long.jpg","width":1920,"height":1080}]}},'
            '"microformat":{"playerMicroformatRenderer":{"publishDate":"2026-06-08","isShortsEligible":false}}};</script>'
        )

        with patch("fengbiao.fetch.youtube_ytdlp.shutil.which", return_value="/opt/homebrew/bin/yt-dlp"), patch(
            "fengbiao.fetch.youtube_ytdlp.subprocess.run", return_value=completed
        ), patch("fengbiao.fetch.youtube_ytdlp.requests.Session") as session_cls:
            session_cls.return_value.get.side_effect = [short_response, long_response]
            videos, skipped = fetch_channel_videos(
                "Name",
                "CHANNEL",
                cutoff,
                ytdlp_path="yt-dlp",
                timeout=30,
                landscape_only=True,
                max_videos=1,
            )

        self.assertIsNone(skipped)
        self.assertEqual([video.platform_video_id for video in videos], ["long1"])

    def test_fetch_channel_videos_uses_flat_playlist_without_cookies(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"entries":[{"id":"new1","title":"New Video","thumbnails":[]}]}',
            stderr="",
        )
        cutoff = datetime(2023, 6, 13, tzinfo=timezone.utc)
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = (
            '<script>var ytInitialPlayerResponse = '
            '{"videoDetails":{"videoId":"new1","title":"New Video","viewCount":"123","thumbnail":{"thumbnails":[]}},'
            '"microformat":{"playerMicroformatRenderer":{"publishDate":"2026-06-09"}}};</script>'
        )

        with patch("fengbiao.fetch.youtube_ytdlp.shutil.which", return_value="/opt/homebrew/bin/yt-dlp"), patch(
            "fengbiao.fetch.youtube_ytdlp.subprocess.run", return_value=completed
        ) as run, patch("fengbiao.fetch.youtube_ytdlp.requests.Session") as session_cls:
            session_cls.return_value.get.return_value = response
            videos, skipped = fetch_channel_videos("Name", "CHANNEL", cutoff, ytdlp_path="yt-dlp", timeout=30)

        self.assertIsNone(skipped)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].play_count, 123)
        cmd = run.call_args.args[0]
        self.assertIn("--flat-playlist", cmd)
        self.assertIn("--dump-single-json", cmd)
        self.assertIn("--playlist-end", cmd)
        self.assertNotIn("--cookies", cmd)
        self.assertNotIn("--cookies-from-browser", cmd)
