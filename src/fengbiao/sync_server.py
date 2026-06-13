from __future__ import annotations

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from fengbiao.ingest import ingest_all
from scripts.export_frontend_snapshot import export_snapshot


ExportFunc = Callable[..., dict[str, Any]]
IngestFunc = Callable[..., dict[str, Any]]


class SyncService:
    def __init__(
        self,
        project_root: str | Path = ".",
        db_path: str | Path = "data/db/fengbiao.sqlite3",
        snapshot_path: str | Path = "apps/web/public/fengbiao-snapshot.json",
        public_covers_dir: str | Path = "apps/web/public/covers",
        creators_path: str | Path = "config/creators.json",
        settings_path: str | Path = "config/settings.json",
        export_func: ExportFunc = export_snapshot,
        ingest_func: IngestFunc = ingest_all,
    ):
        self.project_root = Path(project_root).resolve()
        self.db_path = Path(db_path)
        self.snapshot_path = Path(snapshot_path)
        self.public_covers_dir = Path(public_covers_dir)
        self.creators_path = Path(creators_path)
        self.settings_path = Path(settings_path)
        self.export_func = export_func
        self.ingest_func = ingest_func
        self._lock = threading.Lock()

    def health(self) -> dict[str, Any]:
        db = self._resolve(self.db_path)
        snapshot = self._resolve(self.snapshot_path)
        return {
            "ok": db.exists(),
            "dbExists": db.exists(),
            "snapshotExists": snapshot.exists(),
            "db": str(db),
            "snapshot": str(snapshot),
            "counts": self._counts(db) if db.exists() else None,
        }

    def load_snapshot(self, force_export: bool = False) -> dict[str, Any]:
        with self._lock:
            export_summary = None
            if force_export or not self._resolve(self.snapshot_path).exists():
                export_summary = self.export_func(
                    project_root=self.project_root,
                    db_path=self._resolve(self.db_path),
                    output_path=self._resolve(self.snapshot_path),
                    public_covers_dir=self._resolve(self.public_covers_dir),
                )
            payload = self._read_snapshot()
        return {"payload": payload, "export": export_summary}

    def sync(self, cache_covers: bool = True) -> dict[str, Any]:
        with self._lock:
            with _pushd(self.project_root):
                ingest_summary = self.ingest_func(
                    self.creators_path,
                    self.settings_path,
                    mode="daily",
                    cache_covers=cache_covers,
                )
            export_summary = self.export_func(
                project_root=self.project_root,
                db_path=self._resolve(self.db_path),
                output_path=self._resolve(self.snapshot_path),
                public_covers_dir=self._resolve(self.public_covers_dir),
            )
            payload = self._read_snapshot()
        return {
            "ok": not bool(ingest_summary.get("errors")),
            "ingest": ingest_summary,
            "export": export_summary,
            "snapshot": payload,
        }

    def _read_snapshot(self) -> dict[str, Any]:
        return json.loads(self._resolve(self.snapshot_path).read_text(encoding="utf-8"))

    def _resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else self.project_root / path

    def _counts(self, db: Path) -> dict[str, int] | None:
        try:
            with sqlite3.connect(db) as conn:
                return {
                    "creators": _count(conn, "creators"),
                    "videos": _count(conn, "videos"),
                    "snapshots": _count(conn, "video_snapshots"),
                    "covers": _count(conn, "cover_assets"),
                    "runs": _count(conn, "fetch_runs"),
                }
        except sqlite3.Error:
            return None


def make_handler(service: SyncService) -> type[BaseHTTPRequestHandler]:
    class SyncRequestHandler(BaseHTTPRequestHandler):
        server_version = "FengbiaoSync/0.1"

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._send_common_headers()
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/health":
                    self._send_json(service.health())
                    return
                if parsed.path == "/api/snapshot":
                    query = parse_qs(parsed.query)
                    force_export = query.get("export") == ["1"]
                    self._send_json(service.load_snapshot(force_export=force_export)["payload"])
                    return
                self._send_json({"error": "not found"}, status=404)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            except Exception as exc:  # noqa: BLE001 - API should fail as JSON, not a closed socket.
                self._send_json({"error": str(exc)}, status=500)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path != "/api/sync":
                    self._send_json({"error": "not found"}, status=404)
                    return
                body = self._read_json_body()
                query = parse_qs(parsed.query)
                no_covers = body.get("noCovers") is True or query.get("no_covers") == ["1"]
                result = service.sync(cache_covers=not no_covers)
                self._send_json(result, status=200 if result["ok"] else 500)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            except Exception as exc:  # noqa: BLE001 - keep frontend fallback deterministic.
                self._send_json({"error": str(exc)}, status=500)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return payload if isinstance(payload, dict) else {}

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self._send_common_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_common_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store")

    return SyncRequestHandler


def serve(
    project_root: str | Path = ".",
    host: str = "127.0.0.1",
    port: int = 8765,
    db_path: str | Path = "data/db/fengbiao.sqlite3",
    snapshot_path: str | Path = "apps/web/public/fengbiao-snapshot.json",
    public_covers_dir: str | Path = "apps/web/public/covers",
) -> int:
    service = SyncService(
        project_root=project_root,
        db_path=db_path,
        snapshot_path=snapshot_path,
        public_covers_dir=public_covers_dir,
    )
    server = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"Fengbiao sync server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFengbiao sync server stopped")
    finally:
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Fengbiao frontend/backend sync server.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default="data/db/fengbiao.sqlite3")
    parser.add_argument("--snapshot", default="apps/web/public/fengbiao-snapshot.json")
    parser.add_argument("--public-covers", default="apps/web/public/covers")
    args = parser.parse_args()
    return serve(
        project_root=args.project_root,
        host=args.host,
        port=args.port,
        db_path=args.db,
        snapshot_path=args.snapshot,
        public_covers_dir=args.public_covers,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return int(row[0])


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    raise SystemExit(main())
