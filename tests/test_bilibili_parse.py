import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fengbiao.fetch import bilibili
from fengbiao.fetch.bilibili import parse_user_search


class BilibiliParseTests(unittest.TestCase):
    def test_parse_bilibili_user_search_extracts_creator_and_recent_videos(self):
        payload = json.loads(Path("tests/fixtures/bilibili_search.json").read_text())

        creator, videos = parse_user_search(payload, requested_name="影视飓风", max_recent=5)

        self.assertEqual(creator.platform, "bilibili")
        self.assertEqual(creator.name, "影视飓风")
        self.assertEqual(creator.creator_key, "946974")
        self.assertEqual(creator.follower_count, 16400000)
        self.assertEqual([video.platform_video_id for video in videos], ["BV1RLE16eEX5", "BV16kEC6MEWL"])
        self.assertEqual(videos[0].cover_url, "https://i0.hdslb.com/bfs/archive/cover1.jpg")
        self.assertEqual(videos[0].play_count, 161937)

    def test_fetch_primes_anonymous_session_before_search(self):
        payload = json.loads(Path("tests/fixtures/bilibili_search.json").read_text())
        fake_session = FakeSession(payload)
        bilibili._SESSION = None
        self.addCleanup(lambda: setattr(bilibili, "_SESSION", None))

        with patch.object(bilibili.requests, "Session", return_value=fake_session):
            creator, videos, _ = bilibili.fetch_user_search("影视飓风", "ua", timeout=3, max_recent=2)

        self.assertEqual(creator.creator_key, "946974")
        self.assertEqual(len(videos), 2)
        self.assertIn("https://www.bilibili.com/", fake_session.urls[0])
        self.assertIn("/x/frontend/finger/spi", fake_session.urls[1])
        self.assertIn("/x/web-interface/search/type", fake_session.urls[2])

    def test_expected_mid_allows_configured_name_alias(self):
        payload = json.loads(Path("tests/fixtures/bilibili_search.json").read_text())

        creator, _ = parse_user_search(payload, requested_name="影视飓风别名", max_recent=1, expected_mid="946974")

        self.assertEqual(creator.name, "影视飓风")
        self.assertEqual(creator.creator_key, "946974")

    def test_no_exact_name_or_mid_fails_loudly(self):
        payload = json.loads(Path("tests/fixtures/bilibili_search.json").read_text())

        with self.assertRaises(ValueError):
            parse_user_search(payload, requested_name="不是这个账号", max_recent=1)

        with self.assertRaises(ValueError):
            parse_user_search(payload, requested_name="影视飓风", max_recent=1, expected_mid="not-a-mid")


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        if "/x/web-interface/search/type" in url:
            return FakeResponse(200, self.payload)
        return FakeResponse(200, {"code": 0})


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self.payload
