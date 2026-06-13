# Local Preflight Outline

This is not a Claude Plan. It is a Codex local outline preserved while the requested Fable5 Claude Plan is blocked.

## Suggested MVP Direction

Start with a small, reliable knowledge-base pipeline:

1. Creator config: read a YAML list of Bilibili creator mids.
2. Public metadata fetcher: collect recent公开视频 metadata with conservative rate limits.
3. Storage: save creators, videos, cover assets, and play-count snapshots.
4. Cover cache: download and hash cover images without login state.
5. Reporting: rank recent videos by early growth and summarize title/cover patterns.

## Suggested Stack

- Python for collection and analysis.
- SQLite for the first local database.
- DuckDB or Parquet later if the dataset grows.
- APScheduler or launchd for local scheduled runs.
- pytest for parser, storage, and retry behavior.

## First Implementation Slice

Build the minimum path from `config/creators.yaml` to a local SQLite database and one markdown report. Avoid model training until the raw dataset is stable and traceable.
