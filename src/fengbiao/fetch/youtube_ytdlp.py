from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
import time
from typing import Any

import requests

from fengbiao.models import Video


YOUTUBE_WATCH_URL = "https://www.youtube.com/watch"


def parse_ytdlp_lines(lines: list[str], channel_id: str, cutoff: datetime) -> list[Video]:
    videos: list[Video] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        video = _video_from_ytdlp_item(item, channel_id)
        if video is None:
            continue
        published_at = _parse_datetime(video.published_at)
        if published_at is not None and published_at < cutoff:
            continue
        videos.append(video)
    return videos


def parse_flat_playlist(payload: dict) -> list[dict[str, Any]]:
    entries = payload.get("entries") or []
    result: list[dict[str, Any]] = []
    seen = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        video_id = item.get("id")
        if not isinstance(video_id, str) or not video_id or video_id in seen:
            continue
        seen.add(video_id)
        result.append(item)
    return result


def parse_watch_player_response(
    payload: dict,
    channel_id: str,
    fallback: dict | None = None,
    landscape_only: bool = False,
    min_aspect_ratio: float = 1.6,
) -> Video | None:
    video_details = payload.get("videoDetails") or {}
    microformat = (payload.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    video_id = video_details.get("videoId") or (fallback or {}).get("id")
    if not video_id:
        return None
    if landscape_only and not _is_landscape_player_response(video_details, microformat, fallback, min_aspect_ratio):
        return None
    published_at = _published_at_from_microformat(microformat)
    return Video(
        platform="youtube",
        platform_video_id=video_id,
        creator_key=channel_id,
        title=video_details.get("title") or (fallback or {}).get("title") or "",
        url=f"https://www.youtube.com/watch?v={video_id}",
        cover_url=_thumbnail_url(video_details, video_id, fallback),
        published_at=published_at.isoformat() if published_at else None,
        play_count=_to_int(video_details.get("viewCount")),
        raw={"videoDetails": video_details, "microformat": microformat},
    )


def fetch_channel_videos(
    name: str,
    channel_id: str,
    cutoff: datetime,
    ytdlp_path: str = "yt-dlp",
    timeout: int = 3600,
    playlist_end: int = 2000,
    detail_timeout: int = 20,
    detail_interval_sec: float = 0.25,
    landscape_only: bool = False,
    min_aspect_ratio: float = 1.6,
    max_videos: int | None = None,
) -> tuple[list[Video], str | None]:
    executable = shutil.which(ytdlp_path)
    if executable is None:
        return [], "yt-dlp not found"

    entries, skipped = _fetch_flat_playlist(executable, channel_id, timeout, playlist_end)
    if skipped:
        return [], skipped

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    videos: list[Video] = []
    detail_errors: list[str] = []
    for index, entry in enumerate(entries):
        video_id = entry["id"]
        try:
            payload = _fetch_watch_player_response(session, video_id, detail_timeout)
            video = parse_watch_player_response(payload, channel_id, entry, landscape_only=landscape_only, min_aspect_ratio=min_aspect_ratio)
        except Exception as exc:  # noqa: BLE001 - skip one unavailable video, keep the channel moving.
            detail_errors.append(f"{video_id}: {exc}")
            continue
        if video is None:
            continue
        published_at = _parse_datetime(video.published_at)
        if published_at is not None and published_at < cutoff:
            break
        videos.append(video)
        if max_videos is not None and len(videos) >= int(max_videos):
            break
        if index < len(entries) - 1 and detail_interval_sec > 0:
            time.sleep(detail_interval_sec)

    if not videos and detail_errors:
        return [], "; ".join(detail_errors[:3])
    return videos, None


def _fetch_flat_playlist(executable: str, channel_id: str, timeout: int, playlist_end: int) -> tuple[list[dict[str, Any]], str | None]:
    cmd = [
        executable,
        "--flat-playlist",
        "--dump-single-json",
        "--ignore-errors",
        "--no-warnings",
        "--playlist-end",
        str(int(playlist_end)),
        f"https://www.youtube.com/channel/{channel_id}/videos",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0 and not completed.stdout.strip():
        return [], (completed.stderr or f"yt-dlp exited {completed.returncode}").strip()
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return [], "yt-dlp flat playlist returned invalid JSON"
    return parse_flat_playlist(payload), None


def _fetch_watch_player_response(session: requests.Session, video_id: str, timeout: int, max_retries: int = 2) -> dict:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = session.get(YOUTUBE_WATCH_URL, params={"v": video_id}, timeout=timeout)
            response.raise_for_status()
            return _extract_player_response(response.text)
        except Exception as exc:  # noqa: BLE001 - watch pages can have transient throttles.
            last_error = exc
            if attempt < max_retries:
                time.sleep(2.0 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"failed to fetch youtube watch page for {video_id}")


def _extract_player_response(text: str) -> dict:
    marker = "ytInitialPlayerResponse"
    marker_index = text.find(marker)
    if marker_index < 0:
        raise ValueError("missing ytInitialPlayerResponse")
    brace_index = text.find("{", marker_index)
    if brace_index < 0:
        raise ValueError("missing ytInitialPlayerResponse object")
    payload, _ = json.JSONDecoder().raw_decode(text[brace_index:])
    return payload


def _video_from_ytdlp_item(item: dict, channel_id: str) -> Video | None:
    video_id = item.get("id")
    if not video_id:
        return None
    published_at = _published_at(item)
    return Video(
        platform="youtube",
        platform_video_id=video_id,
        creator_key=channel_id,
        title=item.get("title") or "",
        url=item.get("webpage_url") or item.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        cover_url=_thumbnail_url(item, video_id),
        published_at=published_at.isoformat() if published_at else None,
        play_count=_to_int(item.get("view_count")),
        raw=item,
    )


def _published_at(item: dict) -> datetime | None:
    timestamp = item.get("timestamp")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    upload_date = item.get("upload_date")
    if upload_date:
        try:
            return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _published_at_from_microformat(microformat: dict) -> datetime | None:
    for key in ("publishDate", "uploadDate"):
        value = microformat.get(key)
        if not value:
            continue
        if "T" not in value:
            try:
                return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _thumbnail_url(item: dict, video_id: str, fallback: dict | None = None) -> str:
    thumbnails = (item.get("thumbnail") or {}).get("thumbnails") or item.get("thumbnails") or []
    if not thumbnails and fallback is not None:
        thumbnails = fallback.get("thumbnails") or []
    for thumb in reversed(thumbnails):
        if thumb.get("url"):
            return thumb["url"]
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _is_landscape_player_response(video_details: dict, microformat: dict, fallback: dict | None, min_aspect_ratio: float) -> bool:
    if microformat.get("isShortsEligible") is True:
        return False
    thumbnails = (video_details.get("thumbnail") or {}).get("thumbnails") or []
    if not thumbnails and fallback is not None:
        thumbnails = fallback.get("thumbnails") or []
    ratios = []
    for thumb in thumbnails:
        try:
            width = float(thumb.get("width") or 0)
            height = float(thumb.get("height") or 0)
        except (TypeError, ValueError):
            continue
        if width > 0 and height > 0:
            ratios.append(width / height)
    if not ratios:
        return True
    return max(ratios) >= float(min_aspect_ratio)


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
