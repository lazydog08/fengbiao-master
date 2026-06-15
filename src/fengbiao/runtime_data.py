from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
from typing import Any


def sync_runtime_data(canonical_root: str | Path, runtime_root: str | Path, backup_suffix: str | None = None, force: bool = False) -> dict[str, Any]:
    source_root = Path(canonical_root)
    target_root = Path(runtime_root)
    source_db = source_root / "data/db/fengbiao.sqlite3"
    target_db = target_root / "data/db/fengbiao.sqlite3"
    source_counts = _db_counts(source_db)
    target_counts = _db_counts(target_db)
    result: dict[str, Any] = {
        "source": str(source_root),
        "target": str(target_root),
        "sourceCounts": source_counts,
        "targetCounts": target_counts,
        "dbCopied": False,
        "backup": None,
        "coversCopied": 0,
    }

    if source_counts and (force or _should_replace(source_counts, target_counts)):
        target_db.parent.mkdir(parents=True, exist_ok=True)
        if target_db.exists():
            suffix = backup_suffix or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = target_db.with_name(f"{target_db.name}.backup.{suffix}")
            _copy_sqlite_database(target_db, backup_path)
            result["backup"] = str(backup_path)
        _copy_sqlite_database(source_db, target_db)
        result["dbCopied"] = True
        result["targetCounts"] = source_counts

    result["coversCopied"] = _sync_covers(source_root / "data/covers", target_root / "data/covers")
    return result


def _should_replace(source_counts: dict[str, int], target_counts: dict[str, int] | None) -> bool:
    if target_counts is None:
        return True
    source_videos = source_counts["videos"]
    source_creators = source_counts["creators"]
    target_videos = target_counts["videos"]
    target_creators = target_counts["creators"]
    if source_videos < target_videos or source_creators < target_creators:
        return False
    return source_videos > target_videos or source_creators > target_creators


def _db_counts(path: Path) -> dict[str, int] | None:
    if not path.exists():
        return None
    with sqlite3.connect(path) as conn:
        creators = int(conn.execute("SELECT COUNT(*) FROM creators").fetchone()[0])
        videos = int(conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0])
    return {"creators": creators, "videos": videos}


def _copy_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_name(f".{target.name}.tmp")
    temp_target.unlink(missing_ok=True)
    for sidecar in _sqlite_sidecars(temp_target):
        sidecar.unlink(missing_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_conn, sqlite3.connect(temp_target) as target_conn:
        source_conn.backup(target_conn)
    _remove_sqlite_sidecars(target)
    temp_target.replace(target)
    _remove_sqlite_sidecars(target)


def _remove_sqlite_sidecars(path: Path) -> None:
    for sidecar in _sqlite_sidecars(path):
        sidecar.unlink(missing_ok=True)


def _sqlite_sidecars(path: Path) -> tuple[Path, Path]:
    return (path.with_name(f"{path.name}-wal"), path.with_name(f"{path.name}-shm"))


def _sync_covers(source_dir: Path, target_dir: Path) -> int:
    if not source_dir.exists():
        return 0
    copied = 0
    for source_file in source_dir.rglob("*"):
        if not source_file.is_file():
            continue
        target_file = target_dir / source_file.relative_to(source_dir)
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if not target_file.exists() or source_file.stat().st_mtime > target_file.stat().st_mtime:
            shutil.copy2(source_file, target_file)
            copied += 1
    return copied
