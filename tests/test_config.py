import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fengbiao.config import load_creators


class ConfigTests(unittest.TestCase):
    def test_bilibili_landscape_only_defaults_to_orientation_threshold(self):
        with TemporaryDirectory() as tmp_dir:
            creators_path = Path(tmp_dir) / "creators.json"
            creators_path.write_text(
                json.dumps(
                    {
                        "creators": [
                            {
                                "platform": "bilibili",
                                "name": "飓多多StormCrew",
                                "bili_mid": "1780480185",
                            },
                            {
                                "platform": "youtube",
                                "name": "MKBHD",
                                "yt_channel_id": "CHANNEL",
                            },
                            {
                                "platform": "bilibili",
                                "name": "竖版例外",
                                "bili_mid": "404",
                                "landscape_only": False,
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            bilibili, youtube, vertical_exception = load_creators(creators_path)

            self.assertTrue(bilibili.landscape_only)
            self.assertEqual(bilibili.min_cover_aspect_ratio, 1.0)
            self.assertTrue(youtube.landscape_only)
            self.assertEqual(youtube.min_cover_aspect_ratio, 1.6)
            self.assertFalse(vertical_exception.landscape_only)


if __name__ == "__main__":
    unittest.main()
