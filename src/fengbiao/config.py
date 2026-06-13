from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS = {
    "http": {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "timeout_sec": 20,
        "min_interval_sec": 1.0,
        "max_retries": 2,
    },
    "ingest": {
        "default_max_recent": 6,
        "daily_recent": 5,
    },
    "backfill": {
        "years": 3,
        "bili_page_size": 30,
        "bili_page_interval_sec": 2.0,
        "bili_ytdlp_fallback": True,
        "bili_ytdlp_path": "yt-dlp",
        "bili_ytdlp_timeout_sec": 900,
        "bili_ytdlp_playlist_end": 1200,
        "bili_detail_interval_sec": 0.5,
        "ytdlp_path": "yt-dlp",
        "ytdlp_enabled": True,
        "ytdlp_timeout_sec": 3600,
        "youtube_flat_playlist_end": 2000,
        "youtube_detail_timeout_sec": 20,
        "youtube_detail_interval_sec": 0.25,
    },
    "cover_filters": {
        "reject_dimensions": [[480, 360]],
    },
    "paths": {
        "db": "data/db/fengbiao.sqlite3",
        "covers": "data/covers",
        "logs": "data/logs",
    },
}


@dataclass(frozen=True)
class CreatorConfig:
    platform: str
    name: str
    tags: list[str]
    note: str = ""
    active: bool = True
    bili_mid: str | None = None
    yt_channel_id: str | None = None
    max_recent: int | None = None
    landscape_only: bool = False
    min_cover_aspect_ratio: float = 1.6


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_creators(path: str | Path = "config/creators.json") -> list[CreatorConfig]:
    data = load_json(path)
    creators = []
    for item in data.get("creators", []):
        creators.append(
            CreatorConfig(
                platform=item["platform"],
                name=item["name"],
                tags=list(item.get("tags", [])),
                note=item.get("note", ""),
                active=bool(item.get("active", True)),
                bili_mid=str(item["bili_mid"]) if item.get("bili_mid") else None,
                yt_channel_id=item.get("yt_channel_id"),
                max_recent=item.get("max_recent"),
                landscape_only=bool(item.get("landscape_only", False)),
                min_cover_aspect_ratio=float(item.get("min_cover_aspect_ratio", 1.6)),
            )
        )
    return creators


def load_settings(path: str | Path = "config/settings.json") -> dict[str, Any]:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    p = Path(path)
    if not p.exists():
        return settings
    incoming = load_json(p)
    _deep_update(settings, incoming)
    return settings


def _deep_update(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
