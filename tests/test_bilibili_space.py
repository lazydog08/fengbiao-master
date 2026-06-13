from datetime import datetime, timezone
import unittest

from fengbiao.fetch.bilibili_space import (
    _apply_finger_cookies,
    build_signed_params,
    mixin_key,
    parse_space_archives,
)
import requests


class BilibiliSpaceTests(unittest.TestCase):
    def test_build_signed_params_uses_wbi_mixin_key(self):
        img_key = "7cd084941338484aae1ad9425b84077c"
        sub_key = "4932caff0ff746eab6f01bf08b70ac45"

        signed = build_signed_params(
            {
                "mid": 946974,
                "pn": 1,
                "ps": 30,
                "order": "pubdate",
                "platform": "web",
                "web_location": "1550101",
                "keyword": "",
                "tid": 0,
                "order_avoided": "true",
            },
            img_key,
            sub_key,
            wts=1781336130,
        )

        self.assertEqual(mixin_key(img_key, sub_key), "ea1db124af3c7062474693fa704f4ff8")
        self.assertEqual(signed["w_rid"], "6c1486374ccc8f2f44d7ab310c6332fc")

    def test_parse_space_archives_maps_fields_and_stops_at_cutoff(self):
        payload = {
            "data": {
                "list": {
                    "vlist": [
                        {
                            "bvid": "BVNEW",
                            "title": "新视频",
                            "pic": "http://i0.hdslb.com/bfs/archive/new.jpg",
                            "created": 1781254800,
                            "play": 100,
                            "video_review": 9,
                            "comment": 3,
                        },
                        {
                            "bvid": "BVOLD",
                            "title": "旧视频",
                            "pic": "http://i0.hdslb.com/bfs/archive/old.jpg",
                            "created": 100,
                            "play": 10,
                        },
                    ]
                },
                "page": {"pn": 1, "ps": 30, "count": 2},
            }
        }
        cutoff = datetime(2023, 6, 13, tzinfo=timezone.utc)

        videos, reached_cutoff = parse_space_archives(payload, creator_key="946974", cutoff=cutoff)

        self.assertTrue(reached_cutoff)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].platform_video_id, "BVNEW")
        self.assertEqual(videos[0].title, "新视频")
        self.assertEqual(videos[0].cover_url, "https://i0.hdslb.com/bfs/archive/new.jpg")
        self.assertEqual(videos[0].play_count, 100)
        self.assertEqual(videos[0].danmaku_count, 9)
        self.assertEqual(videos[0].published_at, "2026-06-12T09:00:00+00:00")

    def test_apply_finger_cookies_sets_buvid_values(self):
        session = requests.Session()

        _apply_finger_cookies(session, {"data": {"b_3": "b3-value", "b_4": "b4-value"}})

        self.assertEqual(session.cookies.get("buvid3"), "b3-value")
        self.assertEqual(session.cookies.get("buvid4"), "b4-value")
