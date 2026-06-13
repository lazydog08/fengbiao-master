from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Creator:
    platform: str
    name: str
    creator_key: str
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    note: str = ""
    active: bool = True
    follower_count: int | None = None
    max_recent: int | None = None


@dataclass(frozen=True)
class Video:
    platform: str
    platform_video_id: str
    creator_key: str
    title: str
    url: str
    cover_url: str
    published_at: str | None = None
    play_count: int | None = None
    like_count: int | None = None
    coin_count: int | None = None
    favorite_count: int | None = None
    danmaku_count: int | None = None
    raw: dict[str, Any] | None = None
