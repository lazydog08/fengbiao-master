import unittest
from pathlib import Path

from fengbiao.fetch.youtube import parse_feed


class YouTubeParseTests(unittest.TestCase):
    def test_parse_youtube_feed_extracts_recent_video_metadata(self):
        xml_text = Path("tests/fixtures/youtube_feed.xml").read_text()

        videos = parse_feed(xml_text, channel_id="UCBJycsmduvYEL83R_U4JriQ", max_recent=5)

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].platform, "youtube")
        self.assertEqual(videos[0].platform_video_id, "_gCXmKjDecU")
        self.assertEqual(videos[0].title, "WWDC 2026 Impressions: Yeah, That's About Right")
        self.assertEqual(videos[0].play_count, 3583048)
        self.assertEqual(videos[0].cover_url, "https://i4.ytimg.com/vi/_gCXmKjDecU/hqdefault.jpg")
