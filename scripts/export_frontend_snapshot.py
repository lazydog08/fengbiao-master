from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QUERY = """
SELECT
  v.id,
  c.platform,
  c.name AS creator_name,
  c.tags,
  c.note AS creator_note,
  v.platform_video_id,
  v.title,
  v.url,
  v.published_at,
  v.first_seen_at,
  v.last_seen_at,
  s.play_count,
  s.like_count,
  s.coin_count,
  s.favorite_count,
  s.danmaku_count,
  s.follower_count,
  ca.local_path AS cover_path,
  ca.source_url AS cover_source_url,
  sc.track,
  sc.human_note,
  sc.status,
  sc.metrics_json,
  sc.analysis_json
FROM videos v
JOIN creators c ON c.id = v.creator_id
LEFT JOIN (
  SELECT video_id, MAX(id) AS sample_card_id
  FROM sample_cards
  GROUP BY video_id
) latest_card ON latest_card.video_id = v.id
LEFT JOIN sample_cards sc ON sc.id = latest_card.sample_card_id
LEFT JOIN cover_assets ca ON ca.id = v.current_cover_id
LEFT JOIN (
  SELECT video_id, MAX(id) AS snapshot_id
  FROM video_snapshots
  GROUP BY video_id
) latest ON latest.video_id = v.id
LEFT JOIN video_snapshots s ON s.id = latest.snapshot_id
ORDER BY v.last_seen_at DESC, v.id DESC;
"""


def export_snapshot(
    project_root: str | Path = ".",
    db_path: str | Path = "data/db/fengbiao.sqlite3",
    output_path: str | Path = "apps/web/public/fengbiao-snapshot.json",
    public_covers_dir: str | Path = "apps/web/public/covers",
    cover_max_px: int = 640,
    cover_jpeg_quality: int = 72,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    db = _resolve(root, db_path)
    output = _resolve(root, output_path)
    covers_public = _resolve(root, public_covers_dir)
    covers_staging = covers_public.with_name(f".{covers_public.name}.tmp")
    covers_backup = covers_public.with_name(f".{covers_public.name}.previous")
    output_tmp = output.with_name(f".{output.name}.tmp")

    if not db.exists():
        raise FileNotFoundError(f"SQLite database not found: {db}")

    _remove_path(covers_staging)
    _remove_path(covers_backup)
    _remove_path(output_tmp)
    covers_staging.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    backup_made = False

    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_analysis_column(conn)
            rows = conn.execute(QUERY).fetchall()
            counts = {
                "creators": _count(conn, "creators"),
                "videos": _count(conn, "videos"),
                "samples": len(rows),
            }

        samples = [_row_to_sample(root, covers_staging, row, cover_max_px, cover_jpeg_quality) for row in rows]
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "counts": counts,
            "samples": samples,
            "notes": {
                "scope": "B站样本来自公开搜索结果，通常每账号约 3 条近期视频；这不是全量历史库。",
                "relativeMetric": "库内相对表现基于该创作者当前样本的中位数，不是严格同期对比。",
            },
        }

        output_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if covers_public.exists():
            covers_public.replace(covers_backup)
            backup_made = True
        covers_staging.replace(covers_public)
        output_tmp.replace(output)
        _remove_path(covers_backup)
        copied = sum(1 for item in samples if item["cover"]["url"])
        return {"samples": len(samples), "coversCopied": copied, "output": str(output)}
    except Exception:
        _remove_path(covers_staging)
        _remove_path(output_tmp)
        if backup_made and covers_backup.exists():
            _remove_path(covers_public)
            covers_backup.replace(covers_public)
        raise


def _resolve(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])


def _ensure_analysis_column(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(sample_cards)").fetchall()}
    if "analysis_json" not in columns:
        # Export is sometimes run directly without a prior ingest/init step.
        # Keep the static snapshot path compatible with older local databases.
        conn.execute("ALTER TABLE sample_cards ADD COLUMN analysis_json TEXT")


def _row_to_sample(root: Path, covers_public: Path, row: sqlite3.Row, cover_max_px: int, cover_jpeg_quality: int) -> dict[str, Any]:
    tags = _json_list(row["tags"])
    metrics = _json_object(row["metrics_json"])
    analysis = _json_object(row["analysis_json"]) if row["analysis_json"] else None
    cover_url = _publish_cover(root, covers_public, int(row["id"]), row["cover_path"], cover_max_px, cover_jpeg_quality)
    return {
        "id": int(row["id"]),
        "platform": row["platform"],
        "creator": {
            "name": row["creator_name"],
            "tags": tags,
            "note": "",
        },
        "videoId": row["platform_video_id"],
        "title": row["title"],
        "url": row["url"],
        "publishedAt": row["published_at"],
        "firstSeenAt": row["first_seen_at"],
        "lastSeenAt": row["last_seen_at"],
        "metrics": {
            "playCount": _nullable_int(row["play_count"]),
            "likeCount": _nullable_int(row["like_count"]),
            "coinCount": _nullable_int(row["coin_count"]),
            "favoriteCount": _nullable_int(row["favorite_count"]),
            "danmakuCount": _nullable_int(row["danmaku_count"]),
            "followerCount": _nullable_int(row["follower_count"]),
        },
        "cover": {
            "url": cover_url,
        },
        "card": {
            "track": "",
            "humanNote": "",
            "status": "",
            "baselinePlayCount": _nullable_float(metrics.get("baseline_play_count")),
            "relativeToBaseline": _nullable_float(metrics.get("relative_to_baseline")),
            "viewsPerFollower": _nullable_float(metrics.get("views_per_follower")),
        },
        "analysis": analysis if analysis else None,
    }


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _publish_cover(root: Path, covers_public: Path, video_id: int, cover_path: str | None, cover_max_px: int, cover_jpeg_quality: int) -> str | None:
    if not cover_path:
        return None
    source = _resolve(root, cover_path)
    if not source.exists() or not source.is_file():
        return None
    optimized = covers_public / f"{video_id}.jpg"
    if _optimize_cover(source, optimized, cover_max_px, cover_jpeg_quality):
        return f"/covers/{optimized.name}"
    suffix = source.suffix.lower() if source.suffix else ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    destination = covers_public / f"{video_id}{suffix}"
    shutil.copy2(source, destination)
    return f"/covers/{destination.name}"


def _optimize_cover(source: Path, destination: Path, cover_max_px: int, cover_jpeg_quality: int) -> bool:
    sips = shutil.which("sips")
    if not sips or cover_max_px <= 0:
        return False
    try:
        subprocess.run(
            [
                sips,
                "-s",
                "format",
                "jpeg",
                "-s",
                "formatOptions",
                str(cover_jpeg_quality),
                "-Z",
                str(cover_max_px),
                str(source),
                "--out",
                str(destination),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        _remove_path(destination)
        return False
    return destination.exists() and destination.stat().st_size > 0


def _json_list(raw: str | None) -> list[str]:
    parsed = _loads(raw, [])
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item is not None]


def _json_object(raw: str | None) -> dict[str, Any]:
    parsed = _loads(raw, {})
    return parsed if isinstance(parsed, dict) else {}


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _nullable_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _nullable_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a frontend snapshot for Fengbiao Master.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--db", default="data/db/fengbiao.sqlite3")
    parser.add_argument("--output", default="apps/web/public/fengbiao-snapshot.json")
    parser.add_argument("--public-covers", default="apps/web/public/covers")
    parser.add_argument("--cover-max-px", type=int, default=640)
    parser.add_argument("--cover-jpeg-quality", type=int, default=72)
    args = parser.parse_args()

    summary = export_snapshot(
        project_root=args.project_root,
        db_path=args.db,
        output_path=args.output,
        public_covers_dir=args.public_covers,
        cover_max_px=args.cover_max_px,
        cover_jpeg_quality=args.cover_jpeg_quality,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
