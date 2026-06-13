from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

from fengbiao.models import Creator, Video


YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def parse_feed(xml_text: str, channel_id: str, max_recent: int) -> list[Video]:
    root = ET.fromstring(xml_text)
    videos: list[Video] = []
    for entry in root.findall("atom:entry", NS)[:max_recent]:
        video_id = _text(entry, "yt:videoId")
        if not video_id:
            continue
        title = _text(entry, "atom:title") or ""
        published_at = _text(entry, "atom:published")
        link_el = entry.find("atom:link[@rel='alternate']", NS)
        url = link_el.attrib.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={quote(video_id)}"
        thumb_el = entry.find("media:group/media:thumbnail", NS)
        cover_url = thumb_el.attrib.get("url") if thumb_el is not None else f"https://i.ytimg.com/vi/{quote(video_id)}/hqdefault.jpg"
        stats_el = entry.find("media:group/media:community/media:statistics", NS)
        play_count = _to_int(stats_el.attrib.get("views")) if stats_el is not None else None
        videos.append(
            Video(
                platform="youtube",
                platform_video_id=video_id,
                creator_key=channel_id,
                title=title,
                url=url,
                cover_url=cover_url,
                published_at=published_at,
                play_count=play_count,
            )
        )
    return videos


def fetch_feed(name: str, channel_id: str, user_agent: str, timeout: int, max_recent: int) -> tuple[Creator, list[Video], str]:
    url = YT_FEED_URL.format(channel_id=channel_id)
    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    response.raise_for_status()
    videos = parse_feed(response.text, channel_id=channel_id, max_recent=max_recent)
    creator = Creator(
        platform="youtube",
        name=name,
        creator_key=channel_id,
        url=f"https://www.youtube.com/channel/{channel_id}",
    )
    return creator, videos, url


def _text(node: ET.Element, path: str) -> str | None:
    found = node.find(path, NS)
    return found.text if found is not None else None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
