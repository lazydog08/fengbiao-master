from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
import time

import requests

from fengbiao.fetch.bilibili import normalize_bili_url
from fengbiao.models import Creator, Video


BILIBILI_VIEW_URL = "https://api.bilibili.com/x/web-interface/view"


def parse_flat_entries(lines: list[str]) -> list[str]:
    bvids: list[str] = []
    seen = set()
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        bvid = item.get("id")
        if not isinstance(bvid, str) or not bvid.startswith("BV") or bvid in seen:
            continue
        seen.add(bvid)
        bvids.append(bvid)
    return bvids


def parse_view_detail(payload: dict, creator_key: str, cutoff: datetime) -> tuple[Video, bool]:
    if payload.get("code") != 0:
        raise ValueError(f"bilibili view returned code={payload.get('code')} message={payload.get('message')}")
    data = payload.get("data") or {}
    bvid = data.get("bvid")
    if not bvid:
        raise ValueError("bilibili view response missing bvid")
    pubdate = _to_int(data.get("pubdate"))
    is_old = pubdate is not None and pubdate < int(cutoff.timestamp())
    stat = data.get("stat") or {}
    published_at = datetime.fromtimestamp(pubdate, tz=timezone.utc).isoformat() if pubdate is not None else None
    return (
        Video(
            platform="bilibili",
            platform_video_id=str(bvid),
            creator_key=creator_key,
            title=data.get("title") or "",
            url=f"https://www.bilibili.com/video/{bvid}",
            cover_url=normalize_bili_url(data.get("pic") or ""),
            published_at=published_at,
            play_count=_to_int(stat.get("view")),
            like_count=_to_int(stat.get("like")),
            coin_count=_to_int(stat.get("coin")),
            favorite_count=_to_int(stat.get("favorite")),
            danmaku_count=_to_int(stat.get("danmaku")),
            raw=data,
        ),
        is_old,
    )


def fetch_space_archives_via_ytdlp(
    name: str,
    mid: str,
    user_agent: str,
    timeout: int,
    cutoff: datetime,
    ytdlp_path: str = "yt-dlp",
    ytdlp_timeout: int = 900,
    playlist_end: int = 1200,
    detail_interval_sec: float = 0.5,
) -> tuple[Creator, list[Video], str]:
    source_url = f"https://space.bilibili.com/{mid}/video"
    bvids = _list_space_bvids(source_url, ytdlp_path, ytdlp_timeout, playlist_end)
    if not bvids:
        raise ValueError(f"yt-dlp did not return any bilibili videos for {mid}")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    videos: list[Video] = []
    detail_errors: list[str] = []
    for index, bvid in enumerate(bvids):
        try:
            payload = _fetch_view_detail(session, bvid, timeout)
            video, is_old = parse_view_detail(payload, creator_key=str(mid), cutoff=cutoff)
        except Exception as exc:  # noqa: BLE001 - one missing or hidden video should not fail a creator.
            detail_errors.append(f"{bvid}: {exc}")
            continue
        if is_old:
            break
        videos.append(video)
        if index < len(bvids) - 1 and detail_interval_sec > 0:
            time.sleep(detail_interval_sec)

    if not videos and detail_errors:
        raise ValueError("; ".join(detail_errors[:3]))
    return Creator(platform="bilibili", name=name, creator_key=str(mid), url=source_url), videos, source_url


def _list_space_bvids(source_url: str, ytdlp_path: str, timeout: int, playlist_end: int) -> list[str]:
    executable = shutil.which(ytdlp_path)
    if executable is None:
        raise FileNotFoundError(f"yt-dlp not found: {ytdlp_path}")
    command = [
        executable,
        "--flat-playlist",
        "--dump-json",
        "--ignore-errors",
        "--no-warnings",
        "--playlist-end",
        str(int(playlist_end)),
        source_url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    bvids = parse_flat_entries(result.stdout.splitlines())
    if result.returncode != 0 and not bvids:
        raise ValueError((result.stderr or "").strip() or f"yt-dlp failed with exit code {result.returncode}")
    return bvids


def _fetch_view_detail(session: requests.Session, bvid: str, timeout: int, max_retries: int = 2) -> dict:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = session.get(BILIBILI_VIEW_URL, params={"bvid": bvid}, timeout=timeout)
            if response.status_code in {412, 429}:
                raise ValueError(f"bilibili view request was rate limited with {response.status_code}")
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") in {-352, -412}:
                raise ValueError(f"bilibili view returned code={payload.get('code')} message={payload.get('message')}")
            return payload
        except Exception as exc:  # noqa: BLE001 - details endpoint has transient platform throttles.
            last_error = exc
            if attempt < max_retries:
                time.sleep(3.0 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"failed to fetch bilibili view detail for {bvid}")


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None
