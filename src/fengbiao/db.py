from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator

from fengbiao.metrics import compute_relative_metrics
from fengbiao.models import Creator, Video


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            _migrate_cover_assets_unique_key(conn)

    def upsert_creator(self, creator: Creator) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO creators(platform, name, creator_key, url, tags, note, active, follower_count)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, creator_key) DO UPDATE SET
                  name=excluded.name, url=excluded.url, tags=excluded.tags,
                  note=excluded.note, active=excluded.active,
                  follower_count=COALESCE(excluded.follower_count, creators.follower_count)
                """,
                (
                    creator.platform,
                    creator.name,
                    creator.creator_key,
                    creator.url,
                    json.dumps(creator.tags, ensure_ascii=False),
                    creator.note,
                    1 if creator.active else 0,
                    creator.follower_count,
                ),
            )
            return self._creator_id(conn, creator.platform, creator.creator_key)

    def upsert_cover(self, video_id: int, source_url: str, local_path: str, sha256: str, fetched_at: str) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO cover_assets(video_id, sha256, local_path, source_url, fetched_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(video_id, sha256) DO UPDATE SET source_url=excluded.source_url
                """,
                (video_id, sha256, local_path, source_url, fetched_at),
            )
            row = conn.execute("SELECT id FROM cover_assets WHERE video_id=? AND sha256=?", (video_id, sha256)).fetchone()
            return int(row["id"])

    def upsert_video_with_snapshot(self, creator: Creator, video: Video, cover_id: int | None, fetched_at: str, source_url: str | None = None) -> int:
        with self.connect() as conn:
            creator_id = self._creator_id(conn, creator.platform, creator.creator_key)
            existing = conn.execute(
                "SELECT id, title, current_cover_id FROM videos WHERE platform=? AND platform_video_id=?",
                (video.platform, video.platform_video_id),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO videos(creator_id, platform, platform_video_id, url, title, published_at, first_seen_at, last_seen_at, current_cover_id)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (creator_id, video.platform, video.platform_video_id, video.url, video.title, video.published_at, fetched_at, fetched_at, cover_id),
                )
                video_row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
                video_db_id = int(video_row["id"])
            else:
                video_db_id = int(existing["id"])
                if existing["title"] != video.title:
                    conn.execute(
                        "INSERT INTO change_log(video_id, field, changed_at, old_value, new_value) VALUES(?, 'title', ?, ?, ?)",
                        (video_db_id, fetched_at, existing["title"], video.title),
                    )
                if cover_id and existing["current_cover_id"] and int(existing["current_cover_id"]) != cover_id:
                    conn.execute(
                        "INSERT INTO change_log(video_id, field, changed_at, old_value, new_value) VALUES(?, 'cover', ?, ?, ?)",
                        (video_db_id, fetched_at, str(existing["current_cover_id"]), str(cover_id)),
                    )
                conn.execute(
                    """
                    UPDATE videos SET title=?, url=?, published_at=COALESCE(?, published_at), last_seen_at=?, current_cover_id=COALESCE(?, current_cover_id)
                    WHERE id=?
                    """,
                    (video.title, video.url, video.published_at, fetched_at, cover_id, video_db_id),
                )
            conn.execute(
                """
                INSERT INTO video_snapshots(video_id, fetched_at, source_url, title, cover_url, cover_id, play_count, like_count, coin_count, danmaku_count, favorite_count, follower_count)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_db_id,
                    fetched_at,
                    source_url or video.url,
                    video.title,
                    video.cover_url,
                    cover_id,
                    video.play_count,
                    video.like_count,
                    video.coin_count,
                    video.danmaku_count,
                    video.favorite_count,
                    creator.follower_count,
                ),
            )
            conn.execute(
                "INSERT INTO sample_cards(video_id, status, updated_at) VALUES(?, 'auto', ?) ON CONFLICT(video_id) DO UPDATE SET updated_at=excluded.updated_at",
                (video_db_id, fetched_at),
            )
            return video_db_id

    def video_exists(self, platform: str, platform_video_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM videos WHERE platform=? AND platform_video_id=?",
                (platform, platform_video_id),
            ).fetchone()
            return row is not None

    def attach_cover(self, video_id: int, cover_id: int, fetched_at: str) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT current_cover_id FROM videos WHERE id=?", (video_id,)).fetchone()
            if row is None:
                raise ValueError(f"video not found: {video_id}")
            old_cover_id = row["current_cover_id"]
            if old_cover_id is not None and int(old_cover_id) != cover_id:
                conn.execute(
                    "INSERT INTO change_log(video_id, field, changed_at, old_value, new_value) VALUES(?, 'cover', ?, ?, ?)",
                    (video_id, fetched_at, str(old_cover_id), str(cover_id)),
                )
            conn.execute("UPDATE videos SET current_cover_id=? WHERE id=?", (cover_id, video_id))

    def update_latest_snapshot_cover(self, video_id: int, cover_id: int) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(id) AS id FROM video_snapshots WHERE video_id=?", (video_id,)).fetchone()
            if row and row["id"] is not None:
                conn.execute("UPDATE video_snapshots SET cover_id=? WHERE id=?", (cover_id, row["id"]))

    def delete_videos_cascade(self, video_ids: list[int]) -> int:
        ids = [int(video_id) for video_id in video_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as conn:
            conn.execute(f"UPDATE videos SET current_cover_id=NULL WHERE id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM change_log WHERE video_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM video_snapshots WHERE video_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM sample_cards WHERE video_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM cover_assets WHERE video_id IN ({placeholders})", ids)
            cursor = conn.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", ids)
            return int(cursor.rowcount or 0)

    def start_fetch_run(self, mode: str, started_at: str) -> int:
        with self.connect() as conn:
            conn.execute("INSERT INTO fetch_runs(mode, started_at) VALUES(?, ?)", (mode, started_at))
            row = conn.execute("SELECT last_insert_rowid() AS id").fetchone()
            return int(row["id"])

    def finish_fetch_run(
        self,
        run_id: int,
        finished_at: str,
        creators_checked: int,
        new_videos: int,
        covers_cached: int,
        errors: list[dict[str, Any]],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE fetch_runs
                SET finished_at=?, creators_checked=?, new_videos=?, covers_cached=?, errors_json=?
                WHERE id=?
                """,
                (
                    finished_at,
                    creators_checked,
                    new_videos,
                    covers_cached,
                    json.dumps(errors, ensure_ascii=False),
                    run_id,
                ),
            )

    def refresh_metrics(self) -> None:
        with self.connect() as conn:
            creators = conn.execute("SELECT id, follower_count FROM creators").fetchall()
            for creator in creators:
                rows = conn.execute(
                    """
                    SELECT v.id AS video_id, s.play_count
                    FROM videos v
                    LEFT JOIN (
                        SELECT video_id, MAX(id) AS snapshot_id FROM video_snapshots GROUP BY video_id
                    ) latest ON latest.video_id=v.id
                    LEFT JOIN video_snapshots s ON s.id=latest.snapshot_id
                    WHERE v.creator_id=? AND s.play_count IS NOT NULL
                    """,
                    (creator["id"],),
                ).fetchall()
                counts = [int(row["play_count"]) for row in rows if row["play_count"] is not None]
                for row in rows:
                    metrics = compute_relative_metrics(row["play_count"], counts, creator["follower_count"])
                    conn.execute(
                        "UPDATE sample_cards SET metrics_json=? WHERE video_id=?",
                        (json.dumps(metrics, ensure_ascii=False), row["video_id"]),
                    )

    def count(self, table: str) -> int:
        with self.connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
            return int(row["c"])

    def _creator_id(self, conn: sqlite3.Connection, platform: str, creator_key: str) -> int:
        row = conn.execute("SELECT id FROM creators WHERE platform=? AND creator_key=?", (platform, creator_key)).fetchone()
        if row is None:
            raise ValueError(f"creator not found: {platform}/{creator_key}")
        return int(row["id"])


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS creators(
  id INTEGER PRIMARY KEY,
  platform TEXT NOT NULL,
  name TEXT NOT NULL,
  creator_key TEXT NOT NULL,
  url TEXT,
  tags TEXT NOT NULL DEFAULT '[]',
  note TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  follower_count INTEGER,
  added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(platform, creator_key)
);

CREATE TABLE IF NOT EXISTS videos(
  id INTEGER PRIMARY KEY,
  creator_id INTEGER NOT NULL REFERENCES creators(id),
  platform TEXT NOT NULL,
  platform_video_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  published_at TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  current_cover_id INTEGER REFERENCES cover_assets(id),
  UNIQUE(platform, platform_video_id)
);

CREATE TABLE IF NOT EXISTS video_snapshots(
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  fetched_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  title TEXT NOT NULL,
  cover_url TEXT NOT NULL,
  cover_id INTEGER REFERENCES cover_assets(id),
  play_count INTEGER,
  like_count INTEGER,
  coin_count INTEGER,
  danmaku_count INTEGER,
  favorite_count INTEGER,
  follower_count INTEGER
);

CREATE TABLE IF NOT EXISTS cover_assets(
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  sha256 TEXT NOT NULL,
  local_path TEXT NOT NULL,
  source_url TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  UNIQUE(video_id, sha256)
);

CREATE TABLE IF NOT EXISTS change_log(
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  field TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT
);

CREATE TABLE IF NOT EXISTS sample_cards(
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL UNIQUE REFERENCES videos(id),
  track TEXT,
  human_note TEXT,
  status TEXT NOT NULL DEFAULT 'auto',
  metrics_json TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fetch_runs(
  id INTEGER PRIMARY KEY,
  mode TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  creators_checked INTEGER NOT NULL DEFAULT 0,
  new_videos INTEGER NOT NULL DEFAULT 0,
  covers_cached INTEGER NOT NULL DEFAULT 0,
  errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_videos_creator_id ON videos(creator_id);
CREATE INDEX IF NOT EXISTS idx_video_snapshots_video_id ON video_snapshots(video_id);
CREATE INDEX IF NOT EXISTS idx_cover_assets_video_id ON cover_assets(video_id);
"""


def _migrate_cover_assets_unique_key(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cover_assets'").fetchone()
    if row is None or "sha256 TEXT NOT NULL UNIQUE" not in (row["sql"] or ""):
        return
    conn.execute("ALTER TABLE cover_assets RENAME TO cover_assets_old")
    conn.execute(
        """
        CREATE TABLE cover_assets(
          id INTEGER PRIMARY KEY,
          video_id INTEGER NOT NULL REFERENCES videos(id),
          sha256 TEXT NOT NULL,
          local_path TEXT NOT NULL,
          source_url TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          UNIQUE(video_id, sha256)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO cover_assets(id, video_id, sha256, local_path, source_url, fetched_at)
        SELECT id, video_id, sha256, local_path, source_url, fetched_at
        FROM cover_assets_old
        """
    )
    conn.execute("DROP TABLE cover_assets_old")
