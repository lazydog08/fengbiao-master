from __future__ import annotations

import argparse

from fengbiao.config import load_creators, load_settings
from fengbiao.db import Database
from fengbiao.ingest import backfill_all, ingest_all, summary_to_json


def main() -> int:
    parser = argparse.ArgumentParser(prog="fengbiao", description="封标大师 backend tools")
    parser.add_argument("--creators", default="config/creators.json")
    parser.add_argument("--settings", default="config/settings.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="create or migrate the local SQLite database")

    ingest_parser = subparsers.add_parser("ingest-all", help="fetch configured creator samples")
    ingest_parser.add_argument("--no-covers", action="store_true", help="skip cover image downloads")

    daily_parser = subparsers.add_parser("daily-run", help="daily 10:00 refresh entrypoint")
    daily_parser.add_argument("--no-covers", action="store_true", help="skip cover image downloads")

    backfill_parser = subparsers.add_parser("backfill", help="fetch all configured videos from the last N years")
    backfill_parser.add_argument("--years", type=int, default=None)
    backfill_parser.add_argument("--platform", choices=["all", "bilibili", "youtube"], default="all")
    backfill_parser.add_argument("--creator", default=None)
    backfill_parser.add_argument("--no-covers", action="store_true", help="skip cover image downloads")

    server_parser = subparsers.add_parser("sync-server", help="run the local frontend/backend sync server")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8765)
    server_parser.add_argument("--db", default=None)
    server_parser.add_argument("--snapshot", default="apps/web/public/fengbiao-snapshot.json")
    server_parser.add_argument("--public-covers", default="apps/web/public/covers")

    subparsers.add_parser("list-creators", help="print configured active creators")
    subparsers.add_parser("stats", help="print database row counts")

    args = parser.parse_args()
    if args.command == "init-db":
        settings = load_settings(args.settings)
        Database(settings["paths"]["db"]).init()
        print(summary_to_json({"ok": True, "db": settings["paths"]["db"]}))
        return 0
    if args.command == "ingest-all":
        summary = ingest_all(args.creators, args.settings, mode="initial", cache_covers=not args.no_covers)
        print(summary_to_json(summary))
        return _summary_exit_code(summary)
    if args.command == "daily-run":
        summary = ingest_all(args.creators, args.settings, mode="daily", cache_covers=not args.no_covers)
        print(summary_to_json(summary))
        return _summary_exit_code(summary)
    if args.command == "backfill":
        summary = backfill_all(
            args.creators,
            args.settings,
            years=args.years,
            platform=args.platform,
            only_creator=args.creator,
            cache_covers=not args.no_covers,
        )
        print(summary_to_json(summary))
        return _summary_exit_code(summary)
    if args.command == "sync-server":
        from fengbiao.sync_server import serve

        settings = load_settings(args.settings)
        return serve(
            project_root=".",
            host=args.host,
            port=args.port,
            db_path=args.db or settings["paths"]["db"],
            snapshot_path=args.snapshot,
            public_covers_dir=args.public_covers,
        )
    if args.command == "list-creators":
        creators = [item.__dict__ for item in load_creators(args.creators) if item.active]
        print(summary_to_json({"creators": creators, "count": len(creators)}))
        return 0
    if args.command == "stats":
        settings = load_settings(args.settings)
        db = Database(settings["paths"]["db"])
        db.init()
        print(
            summary_to_json(
                {
                    "creators": db.count("creators"),
                    "videos": db.count("videos"),
                    "snapshots": db.count("video_snapshots"),
                    "covers": db.count("cover_assets"),
                    "runs": db.count("fetch_runs"),
                }
            )
        )
        return 0
    return 2


def _summary_exit_code(summary: dict) -> int:
    if summary.get("creators_checked", 0) == 0:
        return 1
    if summary.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
