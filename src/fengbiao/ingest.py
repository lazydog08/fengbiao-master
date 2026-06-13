from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import time
from pathlib import Path
from typing import Any

from fengbiao.config import CreatorConfig, load_creators, load_settings
from fengbiao.db import Database
from fengbiao.fetch.bilibili import fetch_user_search
from fengbiao.fetch.bilibili_space import BilibiliRiskControlError, fetch_space_archives
from fengbiao.fetch.bilibili_ytdlp import fetch_space_archives_via_ytdlp
from fengbiao.fetch.covers import cache_cover, image_dimensions
from fengbiao.fetch.youtube import fetch_feed
from fengbiao.fetch.youtube_ytdlp import fetch_channel_videos
from fengbiao.models import Creator, Video


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ingest_all(
    creators_path: str | Path = "config/creators.json",
    settings_path: str | Path = "config/settings.json",
    mode: str = "initial",
    cache_covers: bool = True,
) -> dict[str, Any]:
    settings = load_settings(settings_path)
    configs = [item for item in load_creators(creators_path) if item.active]
    db = Database(settings["paths"]["db"])
    db.init()

    started_at = utc_now()
    summary: dict[str, Any] = {
        "mode": mode,
        "started_at": started_at,
        "finished_at": None,
        "creators_checked": 0,
        "videos_seen": 0,
        "new_videos": 0,
        "covers_cached": 0,
        "errors": [],
    }
    fetch_run_id = db.start_fetch_run(mode=mode, started_at=started_at)

    for index, config in enumerate(configs):
        try:
            max_recent = _max_recent(config, settings, mode)
            creator, videos, source_url = fetch_creator(config, settings, max_recent)
            db.upsert_creator(creator)
            summary["creators_checked"] += 1
            _persist_videos(db, creator, videos, source_url, settings, cache_covers, summary)
        except Exception as exc:  # noqa: BLE001 - per-creator isolation is the point here.
            summary["errors"].append({"creator": config.name, "platform": config.platform, "error": str(exc)})
        finally:
            if index < len(configs) - 1:
                time.sleep(float(settings["http"].get("min_interval_sec", 1.0)))

    db.refresh_metrics()
    summary["finished_at"] = utc_now()
    db.finish_fetch_run(
        fetch_run_id,
        finished_at=summary["finished_at"],
        creators_checked=int(summary["creators_checked"]),
        new_videos=int(summary["new_videos"]),
        covers_cached=int(summary["covers_cached"]),
        errors=summary["errors"],
    )
    return summary


def backfill_all(
    creators_path: str | Path = "config/creators.json",
    settings_path: str | Path = "config/settings.json",
    years: int | None = None,
    platform: str = "all",
    only_creator: str | None = None,
    cache_covers: bool = True,
) -> dict[str, Any]:
    settings = load_settings(settings_path)
    configs = [item for item in load_creators(creators_path) if item.active]
    backfill_settings = settings.get("backfill", {})
    years = int(years or backfill_settings.get("years", 3))
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * years)
    db = Database(settings["paths"]["db"])
    db.init()
    started_at = utc_now()
    summary: dict[str, Any] = {
        "mode": "backfill",
        "years": years,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "started_at": started_at,
        "finished_at": None,
        "creators_checked": 0,
        "videos_seen": 0,
        "new_videos": 0,
        "covers_cached": 0,
        "errors": [],
        "skipped": [],
    }
    fetch_run_id = db.start_fetch_run(mode="backfill", started_at=started_at)
    selected = _select_creators(configs, platform, only_creator)
    for index, config in enumerate(selected):
        try:
            creator, videos, source_url = fetch_backfill_creator(config, settings, cutoff)
            db.upsert_creator(creator)
            summary["creators_checked"] += 1
            _persist_videos(db, creator, videos, source_url, settings, cache_covers, summary)
        except SkipCreator as skipped:
            summary["skipped"].append({"creator": config.name, "platform": config.platform, "reason": str(skipped)})
        except Exception as exc:  # noqa: BLE001 - per-creator isolation is intentional.
            summary["errors"].append({"creator": config.name, "platform": config.platform, "stage": "backfill", "error": str(exc)})
        finally:
            if index < len(selected) - 1:
                time.sleep(float(settings["http"].get("min_interval_sec", 1.0)))
    db.refresh_metrics()
    summary["finished_at"] = utc_now()
    db.finish_fetch_run(
        fetch_run_id,
        finished_at=summary["finished_at"],
        creators_checked=int(summary["creators_checked"]),
        new_videos=int(summary["new_videos"]),
        covers_cached=int(summary["covers_cached"]),
        errors=summary["errors"] + summary["skipped"],
    )
    return summary


def fetch_creator(config: CreatorConfig, settings: dict[str, Any], max_recent: int) -> tuple[Creator, list[Video], str]:
    platform = config.platform.lower()
    if platform == "bilibili":
        creator, videos, source_url = fetch_user_search(
            config.name,
            settings["http"]["user_agent"],
            int(settings["http"]["timeout_sec"]),
            max_recent=max_recent,
            expected_mid=config.bili_mid,
        )
    elif platform == "youtube":
        if not config.yt_channel_id:
            raise ValueError(f"missing YouTube channel id for {config.name}")
        if config.landscape_only:
            backfill_settings = settings.get("backfill", {})
            cutoff = datetime.now(timezone.utc) - timedelta(days=365 * int(backfill_settings.get("years", 3)))
            videos, skipped = fetch_channel_videos(
                config.name,
                config.yt_channel_id,
                cutoff,
                ytdlp_path=backfill_settings.get("ytdlp_path", "yt-dlp"),
                timeout=int(backfill_settings.get("ytdlp_timeout_sec", 3600)),
                playlist_end=max(max_recent * 10, 50),
                detail_timeout=int(backfill_settings.get("youtube_detail_timeout_sec", settings["http"]["timeout_sec"])),
                detail_interval_sec=float(backfill_settings.get("youtube_detail_interval_sec", 0.25)),
                landscape_only=True,
                min_aspect_ratio=config.min_cover_aspect_ratio,
                max_videos=max_recent,
            )
            if skipped:
                raise SkipCreator(skipped)
            creator = Creator(
                platform="youtube",
                name=config.name,
                creator_key=config.yt_channel_id,
                url=f"https://www.youtube.com/channel/{config.yt_channel_id}",
            )
            source_url = f"https://www.youtube.com/channel/{config.yt_channel_id}/videos"
        else:
            creator, videos, source_url = fetch_feed(
                config.name,
                config.yt_channel_id,
                settings["http"]["user_agent"],
                int(settings["http"]["timeout_sec"]),
                max_recent=max_recent,
            )
    else:
        raise ValueError(f"unsupported platform: {config.platform}")

    creator = replace(creator, tags=config.tags, note=config.note, active=config.active, max_recent=config.max_recent)
    return creator, videos, source_url


def fetch_backfill_creator(config: CreatorConfig, settings: dict[str, Any], cutoff: datetime) -> tuple[Creator, list[Video], str]:
    platform = config.platform.lower()
    backfill_settings = settings.get("backfill", {})
    if platform == "bilibili":
        if not config.bili_mid:
            raise ValueError(f"missing bilibili mid for {config.name}")
        try:
            creator, videos, source_url = fetch_space_archives(
                config.name,
                config.bili_mid,
                settings["http"]["user_agent"],
                int(settings["http"]["timeout_sec"]),
                cutoff,
                page_size=int(backfill_settings.get("bili_page_size", 30)),
                interval_sec=float(backfill_settings.get("bili_page_interval_sec", 2.0)),
                max_retries=int(settings["http"].get("max_retries", 2)),
            )
        except BilibiliRiskControlError:
            if not bool(backfill_settings.get("bili_ytdlp_fallback", True)):
                raise
            creator, videos, source_url = fetch_space_archives_via_ytdlp(
                config.name,
                config.bili_mid,
                settings["http"]["user_agent"],
                int(settings["http"]["timeout_sec"]),
                cutoff,
                ytdlp_path=backfill_settings.get("bili_ytdlp_path", "yt-dlp"),
                ytdlp_timeout=int(backfill_settings.get("bili_ytdlp_timeout_sec", 900)),
                playlist_end=int(backfill_settings.get("bili_ytdlp_playlist_end", 1200)),
                detail_interval_sec=float(backfill_settings.get("bili_detail_interval_sec", 0.5)),
            )
    elif platform == "youtube":
        if not config.yt_channel_id:
            raise ValueError(f"missing YouTube channel id for {config.name}")
        if not bool(backfill_settings.get("ytdlp_enabled", True)):
            raise SkipCreator("yt-dlp disabled")
        videos, skipped = fetch_channel_videos(
            config.name,
            config.yt_channel_id,
            cutoff,
            ytdlp_path=backfill_settings.get("ytdlp_path", "yt-dlp"),
            timeout=int(backfill_settings.get("ytdlp_timeout_sec", 3600)),
            playlist_end=int(backfill_settings.get("youtube_flat_playlist_end", 2000)),
            detail_timeout=int(backfill_settings.get("youtube_detail_timeout_sec", settings["http"]["timeout_sec"])),
            detail_interval_sec=float(backfill_settings.get("youtube_detail_interval_sec", 0.25)),
            landscape_only=config.landscape_only,
            min_aspect_ratio=config.min_cover_aspect_ratio,
        )
        if skipped:
            raise SkipCreator(skipped)
        creator = Creator(
            platform="youtube",
            name=config.name,
            creator_key=config.yt_channel_id,
            url=f"https://www.youtube.com/channel/{config.yt_channel_id}",
        )
        source_url = f"https://www.youtube.com/channel/{config.yt_channel_id}/videos"
    else:
        raise ValueError(f"unsupported platform: {config.platform}")
    return replace(creator, tags=config.tags, note=config.note, active=config.active, max_recent=config.max_recent), videos, source_url


def _persist_videos(
    db: Database,
    creator: Creator,
    videos: list[Video],
    source_url: str,
    settings: dict[str, Any],
    cache_covers: bool,
    summary: dict[str, Any],
) -> None:
    for video in videos:
        is_new = not db.video_exists(video.platform, video.platform_video_id)
        video_db_id = db.upsert_video_with_snapshot(creator, video, cover_id=None, fetched_at=utc_now(), source_url=source_url)
        cover_id = None
        if cache_covers and video.cover_url:
            try:
                local_path, sha = cache_cover(
                    video.cover_url,
                    settings["paths"]["covers"],
                    video.platform,
                    video.creator_key,
                    video.platform_video_id,
                    settings["http"]["user_agent"],
                    int(settings["http"]["timeout_sec"]),
                    int(settings["http"].get("max_retries", 2)),
                )
                dimensions = image_dimensions(local_path)
                reject_dimensions = {
                    (int(width), int(height))
                    for width, height in settings.get("cover_filters", {}).get("reject_dimensions", [])
                }
                if dimensions in reject_dimensions:
                    db.delete_videos_cascade([video_db_id])
                    summary.setdefault("skipped", []).append(
                        {
                            "creator": creator.name,
                            "platform": creator.platform,
                            "video": video.platform_video_id,
                            "stage": "cover_filter",
                            "reason": "rejected_cover_dimensions",
                            "dimensions": f"{dimensions[0]}x{dimensions[1]}",
                        }
                    )
                    continue
                cover_fetched_at = utc_now()
                cover_id = db.upsert_cover(video_db_id, video.cover_url, local_path, sha, cover_fetched_at)
                db.attach_cover(video_db_id, cover_id, cover_fetched_at)
                summary["covers_cached"] += 1
            except Exception as exc:  # noqa: BLE001 - one bad cover should not skip a creator.
                summary["errors"].append(
                    {
                        "creator": creator.name,
                        "platform": creator.platform,
                        "video": video.platform_video_id,
                        "stage": "cover",
                        "error": str(exc),
                    }
                )
        if cover_id is not None:
            db.update_latest_snapshot_cover(video_db_id, cover_id)
        if is_new:
            summary["new_videos"] += 1
        summary["videos_seen"] += 1


def _select_creators(configs: list[CreatorConfig], platform: str, only_creator: str | None) -> list[CreatorConfig]:
    platform = platform.lower()
    selected = []
    for config in configs:
        if platform != "all" and config.platform.lower() != platform:
            continue
        if only_creator and config.name != only_creator:
            continue
        selected.append(config)
    return selected


class SkipCreator(Exception):
    pass


def _max_recent(config: CreatorConfig, settings: dict[str, Any], mode: str) -> int:
    if config.max_recent is not None:
        return int(config.max_recent)
    key = "daily_recent" if mode == "daily" else "default_max_recent"
    return int(settings["ingest"][key])


def summary_to_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
