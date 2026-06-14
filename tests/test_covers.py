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


def _minimal_gif_header(width: int, height: int) -> bytes:
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little") + b"\x00\x00\x00"


def _minimal_webp_vp8x(width: int, height: int) -> bytes:
    payload = (
        b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    riff_size = 4 + 8 + len(payload)
    return b"RIFF" + riff_size.to_bytes(4, "little") + b"WEBP" + b"VP8X" + len(payload).to_bytes(4, "little") + payload


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

    def test_image_dimensions_reads_webp_and_gif_sizes(self):
        with TemporaryDirectory() as tmp_dir:
            webp = Path(tmp_dir) / "cover.webp"
            gif = Path(tmp_dir) / "cover.gif"
            webp.write_bytes(_minimal_webp_vp8x(720, 1280))
            gif.write_bytes(_minimal_gif_header(640, 960))

            self.assertEqual(image_dimensions(webp), (720, 1280))
            self.assertEqual(image_dimensions(gif), (640, 960))

    def test_rejected_cover_dimensions_matches_exact_size(self):
        with TemporaryDirectory() as tmp_dir:
            vertical_wrapper = Path(tmp_dir) / "vertical-wrapper.png"
            landscape = Path(tmp_dir) / "landscape.png"
            vertical_wrapper.write_bytes(_minimal_png_header(480, 360))
            landscape.write_bytes(_minimal_png_header(1280, 720))

            self.assertTrue(is_rejected_cover_dimensions(vertical_wrapper, [[480, 360]]))
            self.assertFalse(is_rejected_cover_dimensions(landscape, [[480, 360]]))

    def test_below_min_aspect_ratio_detects_non_landscape_covers(self):
        from fengbiao.fetch.covers import is_below_min_aspect_ratio

        with TemporaryDirectory() as tmp_dir:
            portrait = Path(tmp_dir) / "portrait.png"
            landscape = Path(tmp_dir) / "landscape.png"
            boundary = Path(tmp_dir) / "boundary.png"
            unknown = Path(tmp_dir) / "unknown.webp"
            portrait.write_bytes(_minimal_png_header(720, 1280))
            landscape.write_bytes(_minimal_png_header(1280, 720))
            boundary.write_bytes(_minimal_png_header(1600, 1000))
            portrait_webp = Path(tmp_dir) / "portrait.webp"
            portrait_webp.write_bytes(_minimal_webp_vp8x(720, 1280))
            unknown.write_bytes(b"not-a-known-image")

            self.assertTrue(is_below_min_aspect_ratio(portrait, 1.6))
            self.assertTrue(is_below_min_aspect_ratio(portrait_webp, 1.0))
            self.assertFalse(is_below_min_aspect_ratio(landscape, 1.6))
            self.assertFalse(is_below_min_aspect_ratio(boundary, 1.6))
            self.assertFalse(is_below_min_aspect_ratio(unknown, 1.6))
