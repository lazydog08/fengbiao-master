from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote, urlencode

import requests

from fengbiao.models import Creator, Video


BILIBILI_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
BILIBILI_HOME_URL = "https://www.bilibili.com/"
BILIBILI_FINGER_URL = "https://api.bilibili.com/x/frontend/finger/spi"
_SESSION: requests.Session | None = None


def normalize_bili_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def parse_user_search(payload: dict, requested_name: str, max_recent: int, expected_mid: str | None = None) -> tuple[Creator, list[Video]]:
    results = payload.get("data", {}).get("result") or []
    if not results:
        raise ValueError(f"no bilibili creator found for {requested_name}")
    chosen = _choose_result(results, requested_name, expected_mid)
    creator_key = str(chosen["mid"])
    creator = Creator(
        platform="bilibili",
        name=chosen.get("uname") or requested_name,
        creator_key=creator_key,
        url=f"https://space.bilibili.com/{creator_key}",
        follower_count=_to_int(chosen.get("fans")),
    )
    videos = []
    for item in (chosen.get("res") or [])[:max_recent]:
        bvid = item.get("bvid")
        if not bvid:
            continue
        published_at = None
        if item.get("pubdate"):
            published_at = datetime.fromtimestamp(int(item["pubdate"]), tz=timezone.utc).isoformat()
        videos.append(
            Video(
                platform="bilibili",
                platform_video_id=bvid,
                creator_key=creator_key,
                title=_clean_title(item.get("title") or ""),
                url=f"https://www.bilibili.com/video/{bvid}",
                cover_url=normalize_bili_url(item.get("pic") or ""),
                published_at=published_at,
                play_count=_to_int(item.get("play")),
                coin_count=_to_int(item.get("coin")),
                favorite_count=_to_int(item.get("fav")),
                danmaku_count=_to_int(item.get("dm")),
                raw=item,
            )
        )
    return creator, videos


def fetch_user_search(name: str, user_agent: str, timeout: int, max_recent: int, expected_mid: str | None = None) -> tuple[Creator, list[Video], str]:
    params = {"search_type": "bili_user", "keyword": name}
    url = BILIBILI_SEARCH_URL + "?" + urlencode(params, quote_via=quote)
    session = _get_session(user_agent, timeout)
    response = session.get(url, timeout=timeout)
    if response.status_code == 412:
        session = _reset_session(user_agent, timeout)
        response = session.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(f"bilibili search returned code={payload.get('code')} message={payload.get('message')}")
    creator, videos = parse_user_search(payload, requested_name=name, max_recent=max_recent, expected_mid=expected_mid)
    return creator, videos, url


def _get_session(user_agent: str, timeout: int) -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _new_session(user_agent, timeout)
    return _SESSION


def _reset_session(user_agent: str, timeout: int) -> requests.Session:
    global _SESSION
    _SESSION = _new_session(user_agent, timeout)
    return _SESSION


def _new_session(user_agent: str, timeout: int) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Referer": BILIBILI_HOME_URL,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    session.get(BILIBILI_HOME_URL, timeout=timeout)
    session.get(BILIBILI_FINGER_URL, timeout=timeout)
    return session


def _choose_result(results: list[dict], requested_name: str, expected_mid: str | None = None) -> dict:
    if expected_mid:
        for item in results:
            if str(item.get("mid")) == str(expected_mid):
                return item
        raise ValueError(f"bilibili creator {requested_name} did not match expected mid {expected_mid}")
    for item in results:
        if item.get("uname") == requested_name:
            return item
    raise ValueError(f"bilibili creator exact name not found: {requested_name}")


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _clean_title(title: str) -> str:
    return title.replace("<em class=\"keyword\">", "").replace("</em>", "")
