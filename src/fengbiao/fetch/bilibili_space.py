from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import time
from urllib.parse import quote, urlencode

import requests

from fengbiao.fetch.bilibili import normalize_bili_url
from fengbiao.models import Creator, Video


BILIBILI_NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
BILIBILI_SPACE_ARCHIVE_URL = "https://api.bilibili.com/x/space/wbi/arc/search"
BILIBILI_HOME_URL = "https://www.bilibili.com/"
BILIBILI_FINGER_URL = "https://api.bilibili.com/x/frontend/finger/spi"
MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


@dataclass
class WbiKeys:
    img_key: str
    sub_key: str
    fetched_at: float


_SESSION: requests.Session | None = None
_WBI_KEYS: WbiKeys | None = None


def mixin_key(img_key: str, sub_key: str) -> str:
    source = img_key + sub_key
    return "".join(source[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def build_signed_params(params: dict, img_key: str, sub_key: str, wts: int | None = None) -> dict:
    signed = dict(params)
    signed["wts"] = int(time.time()) if wts is None else int(wts)
    filtered = {key: _filter_value(value) for key, value in signed.items()}
    query = urlencode(sorted(filtered.items()), quote_via=quote)
    signed["w_rid"] = hashlib.md5((query + mixin_key(img_key, sub_key)).encode("utf-8")).hexdigest()
    return signed


def parse_space_archives(payload: dict, creator_key: str, cutoff: datetime) -> tuple[list[Video], bool]:
    videos: list[Video] = []
    reached_cutoff = False
    cutoff_ts = int(cutoff.timestamp())
    for item in payload.get("data", {}).get("list", {}).get("vlist", []) or []:
        created = _to_int(item.get("created"))
        if created is not None and created < cutoff_ts:
            reached_cutoff = True
            break
        bvid = item.get("bvid")
        if not bvid:
            continue
        published_at = None
        if created is not None:
            published_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
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
                danmaku_count=_to_int(item.get("video_review")),
                raw=item,
            )
        )
    return videos, reached_cutoff


def fetch_space_archives(
    name: str,
    mid: str,
    user_agent: str,
    timeout: int,
    cutoff: datetime,
    page_size: int = 30,
    interval_sec: float = 2.0,
    max_retries: int = 2,
) -> tuple[Creator, list[Video], str]:
    all_videos: list[Video] = []
    page = 1
    source_url = f"https://space.bilibili.com/{mid}/video"
    while True:
        session = _get_session(user_agent, timeout, mid)
        payload = _fetch_archive_page(session, mid, page, page_size, timeout, max_retries)
        page_videos, reached_cutoff = parse_space_archives(payload, creator_key=str(mid), cutoff=cutoff)
        all_videos.extend(page_videos)
        page_info = payload.get("data", {}).get("page", {}) or {}
        count = _to_int(page_info.get("count")) or 0
        ps = _to_int(page_info.get("ps")) or page_size
        vlist = payload.get("data", {}).get("list", {}).get("vlist", []) or []
        if reached_cutoff or not vlist or page * ps >= count:
            break
        page += 1
        time.sleep(interval_sec)
    creator = Creator(platform="bilibili", name=name, creator_key=str(mid), url=source_url)
    return creator, all_videos, source_url


def _fetch_archive_page(session: requests.Session, mid: str, page: int, page_size: int, timeout: int, max_retries: int) -> dict:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        keys = _get_wbi_keys(session, timeout)
        params = build_signed_params(
            {
                "mid": mid,
                "pn": page,
                "ps": page_size,
                "order": "pubdate",
                "platform": "web",
                "web_location": "1550101",
                "keyword": "",
                "tid": 0,
                "order_avoided": "true",
            },
            keys.img_key,
            keys.sub_key,
        )
        try:
            response = session.get(BILIBILI_SPACE_ARCHIVE_URL, params=params, timeout=timeout)
            if response.status_code == 412:
                _reset_state()
                session = _get_session(session.headers.get("User-Agent", "Mozilla/5.0"), timeout, mid)
                raise BilibiliRiskControlError("bilibili space request was banned with 412")
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                if payload.get("code") == -352:
                    _reset_state()
                    raise BilibiliRiskControlError(f"bilibili space returned code=-352 message={payload.get('message')}")
                raise ValueError(f"bilibili space returned code={payload.get('code')} message={payload.get('message')}")
            return payload
        except Exception as exc:  # noqa: BLE001 - retry wraps transport and platform errors.
            last_error = exc
            if attempt < max_retries:
                if isinstance(exc, BilibiliRiskControlError):
                    session = _get_session(session.headers.get("User-Agent", "Mozilla/5.0"), timeout, mid)
                    time.sleep(8.0 * (attempt + 1))
                else:
                    time.sleep(1.0 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError("failed to fetch bilibili space page")


def _get_session(user_agent: str, timeout: int, mid: str) -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(
            {
                "User-Agent": user_agent,
                "Referer": f"https://space.bilibili.com/{mid}/video",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Origin": "https://space.bilibili.com",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            }
        )
        _SESSION.get(BILIBILI_HOME_URL, timeout=timeout)
        finger_response = _SESSION.get(BILIBILI_FINGER_URL, timeout=timeout)
        _apply_finger_cookies(_SESSION, finger_response.json())
        _SESSION.get(f"https://space.bilibili.com/{mid}/video", timeout=timeout)
    else:
        _SESSION.headers.update({"Referer": f"https://space.bilibili.com/{mid}/video"})
    return _SESSION


def _get_wbi_keys(session: requests.Session, timeout: int) -> WbiKeys:
    global _WBI_KEYS
    now = time.time()
    if _WBI_KEYS and now - _WBI_KEYS.fetched_at < 3600:
        return _WBI_KEYS
    response = session.get(BILIBILI_NAV_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    wbi_img = payload.get("data", {}).get("wbi_img", {})
    img_key = _key_from_url(wbi_img.get("img_url") or "")
    sub_key = _key_from_url(wbi_img.get("sub_url") or "")
    if not img_key or not sub_key:
        raise ValueError("missing bilibili WBI keys")
    _WBI_KEYS = WbiKeys(img_key=img_key, sub_key=sub_key, fetched_at=now)
    return _WBI_KEYS


def _reset_state() -> None:
    global _SESSION, _WBI_KEYS
    _SESSION = None
    _WBI_KEYS = None


def _key_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1].split(".", 1)[0]


def _filter_value(value) -> str:
    return "".join(char for char in str(value) if char not in "!'()*")


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _clean_title(title: str) -> str:
    return title.replace('<em class="keyword">', "").replace("</em>", "")


def _apply_finger_cookies(session: requests.Session, payload: dict) -> None:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    b3 = data.get("b_3")
    b4 = data.get("b_4")
    if b3:
        session.cookies.set("buvid3", b3, domain=".bilibili.com", path="/")
    if b4:
        session.cookies.set("buvid4", b4, domain=".bilibili.com", path="/")


class BilibiliRiskControlError(ValueError):
    pass
