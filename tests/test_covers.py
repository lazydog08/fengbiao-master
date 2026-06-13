import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fengbiao.fetch.covers import _cover_candidates, image_dimensions, is_rejected_cover_dimensions


def _minimal_png_header(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + (13).to_bytes(4, "big")
        + b"IHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )


class CoverDownloadTests(unittest.TestCase):
    def test_bilibili_cover_candidates_try_https_alternates_before_http(self):
        candidates = _cover_candidates("https://i0.hdslb.com/bfs/archive/a.jpg")

        self.assertEqual(candidates[0], "https://i0.hdslb.com/bfs/archive/a.jpg")
        self.assertIn("https://i1.hdslb.com/bfs/archive/a.jpg", candidates[:5])
        self.assertIn("https://i2.hdslb.com/bfs/archive/a.jpg", candidates[:5])
        self.assertLess(
            candidates.index("https://i1.hdslb.com/bfs/archive/a.jpg"),
            candidates.index("http://i1.hdslb.com/bfs/archive/a.jpg"),
        )

    def test_image_dimensions_reads_png_size(self):
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cover.png"
            path.write_bytes(_minimal_png_header(1280, 720))

            self.assertEqual(image_dimensions(path), (1280, 720))

    def test_rejected_cover_dimensions_matches_exact_size(self):
        with TemporaryDirectory() as tmp_dir:
            vertical_wrapper = Path(tmp_dir) / "vertical-wrapper.png"
            landscape = Path(tmp_dir) / "landscape.png"
            vertical_wrapper.write_bytes(_minimal_png_header(480, 360))
            landscape.write_bytes(_minimal_png_header(1280, 720))

            self.assertTrue(is_rejected_cover_dimensions(vertical_wrapper, [[480, 360]]))
            self.assertFalse(is_rejected_cover_dimensions(landscape, [[480, 360]]))
