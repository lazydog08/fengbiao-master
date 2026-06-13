from __future__ import annotations

import hashlib
from pathlib import Path
import re
import time
from urllib.parse import urlparse, urlunparse

import requests
from requests.exceptions import SSLError


ImageDimensions = tuple[int, int]


def cache_cover(
    url: str,
    root: str | Path,
    platform: str,
    creator_key: str,
    video_id: str,
    user_agent: str,
    timeout: int,
    max_retries: int = 2,
) -> tuple[str, str]:
    if not url:
        raise ValueError("missing cover url")
    headers = {"User-Agent": user_agent}
    if "hdslb.com" in url:
        headers["Referer"] = "https://www.bilibili.com/"
    response = _get_with_retries(url, headers=headers, timeout=timeout, max_retries=max_retries)
    content = response.content
    _validate_image_response(response, content)
    sha = hashlib.sha256(content).hexdigest()
    suffix = Path(urlparse(url).path).suffix or ".jpg"
    out_dir = Path(root) / _safe_component(platform) / _safe_component(creator_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_component(video_id)}_{sha[:8]}{suffix}"
    if not out_path.exists():
        out_path.write_bytes(content)
    return str(out_path), sha


def _get_with_retries(url: str, headers: dict[str, str], timeout: int, max_retries: int) -> requests.Response:
    last_error: Exception | None = None
    candidates = _cover_candidates(url)
    for candidate in candidates:
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(candidate, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response
            except SSLError as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
                continue
            except requests.RequestException as exc:
                last_error = exc
                if attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
                continue
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"failed to fetch cover: {url}")


def _cover_candidates(url: str) -> list[str]:
    parsed = urlparse(url)
    candidates = [url]
    if "hdslb.com" not in parsed.netloc:
        return candidates
    hosts = [parsed.netloc, "i0.hdslb.com", "i1.hdslb.com", "i2.hdslb.com", "archive.biliimg.com"]
    for scheme in ["https", "http"]:
        for host in hosts:
            candidate = urlunparse((scheme, host, parsed.path, "", parsed.query, ""))
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _validate_image_response(response: requests.Response, content: bytes, max_bytes: int = 20 * 1024 * 1024) -> None:
    if len(content) == 0:
        raise ValueError("empty cover response")
    if len(content) > max_bytes:
        raise ValueError(f"cover response too large: {len(content)} bytes")
    content_type = (response.headers.get("content-type") or "").lower()
    looks_like_image = (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith(b"RIFF")
        or content.startswith(b"GIF8")
    )
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"cover response is not an image: {content_type}")
    if not looks_like_image and not content_type.startswith("image/"):
        raise ValueError("cover response does not look like an image")


def image_dimensions(path: str | Path) -> ImageDimensions | None:
    data = Path(path).read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(data)
    return None


def is_rejected_cover_dimensions(path: str | Path, reject_dimensions: list[list[int]] | list[tuple[int, int]]) -> bool:
    dimensions = image_dimensions(path)
    if dimensions is None:
        return False
    rejected = {(int(width), int(height)) for width, height in reject_dimensions}
    return dimensions in rejected


def _jpeg_dimensions(data: bytes) -> ImageDimensions | None:
    offset = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            return None
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(data):
            return None
        if marker in sof_markers and segment_length >= 7:
            segment = data[offset : offset + segment_length]
            height = int.from_bytes(segment[3:5], "big")
            width = int.from_bytes(segment[5:7], "big")
            return width, height
        offset += segment_length
    return None


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not safe:
        raise ValueError("empty safe path component")
    return safe
