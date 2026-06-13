#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlencode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fengbiao.config import load_creators, load_settings  # noqa: E402
from fengbiao.db import Database  # noqa: E402
from fengbiao.fetch.bilibili_space import (  # noqa: E402
    BILIBILI_SPACE_ARCHIVE_URL,
    _get_session,
    _get_wbi_keys,
    _reset_state,
    build_signed_params,
    parse_space_archives,
)
from fengbiao.ingest import _persist_videos, utc_now  # noqa: E402
from fengbiao.models import Creator  # noqa: E402


APPLE_SCRIPT = r'''
on findJson(e, depth, maxDepth)
  tell application "System Events"
    try
      set valText to value of e as text
      if valText starts with "{\"code\"" then return valText
    end try
    if depth < maxDepth then
      try
        set kids to UI elements of e
        repeat with k in kids
          set foundText to my findJson(k, depth + 1, maxDepth)
          if foundText is not "" then return foundText
        end repeat
      end try
    end if
    return ""
  end tell
end findJson

on findExpectedJsonInChromeWindows(expectedNeedle)
  tell application "System Events"
    tell process "Google Chrome"
      repeat with w in windows
        set foundText to my findJson(w, 0, 12)
        if foundText is not "" and foundText contains expectedNeedle then return foundText
      end repeat
    end tell
  end tell
  return ""
end findExpectedJsonInChromeWindows

on run argv
  set targetUrl to item 1 of argv
  set waitSeconds to item 2 of argv as real
  set expectedNeedle to item 3 of argv
  tell application "System Events"
    tell process "Google Chrome"
      set frontmost to true
      delay 0.2
      -- Stay within the same visible Chrome instance. This Mac can also have
      -- a separate collector Chrome, so AppleScript app-level navigation can
      -- update one instance while accessibility reads another.
      keystroke "l" using command down
      delay 0.2
      set addressField to value of attribute "AXFocusedUIElement"
      set value of addressField to targetUrl
      key code 36
      delay waitSeconds
      repeat with i from 1 to 60
        set txt to my findExpectedJsonInChromeWindows(expectedNeedle)
        if txt is not "" then return txt
        delay 0.5
      end repeat
    end tell
  end tell
  return ""
end run
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Bilibili via the user's logged-in Chrome page response.")
    parser.add_argument("--creators", default="config/creators.json")
    parser.add_argument("--settings", default="config/settings.json")
    parser.add_argument("--creator", default=None, help="Exact creator name to backfill.")
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--no-covers", action="store_true")
    parser.add_argument("--page-delay", type=float, default=2.0)
    parser.add_argument("--between-pages", type=float, default=1.0)
    args = parser.parse_args()

    summary = backfill_bilibili_chrome(
        creators_path=args.creators,
        settings_path=args.settings,
        only_creator=args.creator,
        years=args.years,
        cache_covers=not args.no_covers,
        page_delay=args.page_delay,
        between_pages=args.between_pages,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if summary["errors"] else 0


def backfill_bilibili_chrome(
    creators_path: str | Path,
    settings_path: str | Path,
    only_creator: str | None,
    years: int | None,
    cache_covers: bool,
    page_delay: float,
    between_pages: float,
) -> dict[str, Any]:
    settings = load_settings(settings_path)
    configs = [item for item in load_creators(creators_path) if item.active and item.platform.lower() == "bilibili"]
    if only_creator:
        configs = [item for item in configs if item.name == only_creator]

    years = int(years or settings.get("backfill", {}).get("years", 3))
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * years)
    db = Database(settings["paths"]["db"])
    db.init()

    started_at = utc_now()
    run_id = db.start_fetch_run(mode="backfill-chrome", started_at=started_at)
    summary: dict[str, Any] = {
        "mode": "backfill-chrome",
        "years": years,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "started_at": started_at,
        "finished_at": None,
        "creators_checked": 0,
        "videos_seen": 0,
        "new_videos": 0,
        "covers_cached": 0,
        "errors": [],
    }

    for config in configs:
        if not config.bili_mid:
            summary["errors"].append({"creator": config.name, "stage": "config", "error": "missing bili_mid"})
            continue
        creator = Creator(
            platform="bilibili",
            name=config.name,
            creator_key=config.bili_mid,
            url=f"https://space.bilibili.com/{config.bili_mid}/video",
        )
        creator = replace(creator, tags=config.tags, note=config.note, active=config.active, max_recent=config.max_recent)
        db.upsert_creator(creator)
        source_url = creator.url or f"https://space.bilibili.com/{config.bili_mid}/video"
        try:
            pages = 0
            for payload in iter_chrome_space_pages(
                config.bili_mid,
                settings,
                cutoff,
                page_delay=page_delay,
                between_pages=between_pages,
            ):
                pages += 1
                videos, reached_cutoff = parse_space_archives(payload, creator_key=config.bili_mid, cutoff=cutoff)
                _persist_videos(db, creator, videos, source_url, settings, cache_covers, summary)
                if reached_cutoff:
                    break
            summary["creators_checked"] += 1
            summary.setdefault("pages", {})[config.name] = pages
        except Exception as exc:  # noqa: BLE001 - keep other creators moving.
            summary["errors"].append({"creator": config.name, "stage": "chrome-backfill", "error": str(exc)})

    db.refresh_metrics()
    summary["finished_at"] = utc_now()
    db.finish_fetch_run(
        run_id,
        finished_at=summary["finished_at"],
        creators_checked=int(summary["creators_checked"]),
        new_videos=int(summary["new_videos"]),
        covers_cached=int(summary["covers_cached"]),
        errors=summary["errors"],
    )
    return summary


def iter_chrome_space_pages(mid: str, settings: dict[str, Any], cutoff: datetime, page_delay: float, between_pages: float):
    _reset_state()
    session = _get_session(settings["http"]["user_agent"], int(settings["http"]["timeout_sec"]), mid)
    keys = _get_wbi_keys(session, int(settings["http"]["timeout_sec"]))
    page = 1
    page_size = int(settings.get("backfill", {}).get("bili_page_size", 30))
    cutoff_ts = int(cutoff.timestamp())

    while True:
        url = signed_space_url(mid, page, page_size, keys.img_key, keys.sub_key)
        payload = fetch_json_via_chrome(url, page_delay, expected_page=page)
        if payload.get("code") != 0:
            raise ValueError(f"bilibili chrome page returned code={payload.get('code')} message={payload.get('message')}")
        page_info = payload.get("data", {}).get("page", {}) or {}
        if int(page_info.get("pn") or page) != page:
            raise ValueError(f"stale chrome response: expected page {page}, got {page_info.get('pn')}")
        yield payload

        vlist = payload.get("data", {}).get("list", {}).get("vlist", []) or []
        if not vlist:
            break
        oldest_created = min((int(item.get("created") or 0) for item in vlist), default=0)
        if oldest_created and oldest_created < cutoff_ts:
            break
        count = int(page_info.get("count") or 0)
        ps = int(page_info.get("ps") or page_size)
        if page * ps >= count:
            break
        page += 1
        time.sleep(between_pages)


def signed_space_url(mid: str, page: int, page_size: int, img_key: str, sub_key: str) -> str:
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
        img_key,
        sub_key,
    )
    return BILIBILI_SPACE_ARCHIVE_URL + "?" + urlencode(params)


def fetch_json_via_chrome(url: str, page_delay: float, expected_page: int) -> dict[str, Any]:
    expected_needle = f'"pn":{expected_page}'
    completed = subprocess.run(
        ["osascript", "-e", APPLE_SCRIPT, url, str(page_delay), expected_needle],
        capture_output=True,
        text=True,
        timeout=max(45, int(page_delay + 35)),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    text = completed.stdout.strip()
    if not text:
        raise ValueError("Chrome page did not expose JSON text")
    return json.loads(text)


if __name__ == "__main__":
    raise SystemExit(main())
