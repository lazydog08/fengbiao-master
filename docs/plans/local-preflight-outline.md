# Local Preflight Outline

This is not a Claude Plan. It is a Codex local outline preserved while the requested Fable5 Claude Plan is blocked.

## Suggested MVP Direction

Start with a small, reliable sample-card pipeline:

1. Creator config: read Xiaohei's own Bilibili mid plus a YAML list of 10 to 30 benchmark creator mids.
2. Public metadata fetcher: collect recent公开视频 metadata with conservative rate limits.
3. Storage: save creators, videos, cover assets, creator follower counts, play-count snapshots, and title/cover change events.
4. Metrics: calculate each video's relative performance against that creator's own baseline and first-48-hour growth.
5. Cover cache: download and hash cover images without login state.
6. Reporting: render topic-lane sample cards instead of a pure play-count dashboard.

## Suggested Stack

- Python for collection and analysis.
- SQLite for the first local database.
- DuckDB or Parquet later if the dataset grows.
- APScheduler or launchd for local scheduled runs.
- pytest for parser, storage, and retry behavior.

## First Implementation Slice

Build the minimum path from `config/creators.yaml` to a local SQLite database and one sample-card reference wall. Avoid model training, OCR, and visual feature extraction until the raw dataset, relative metrics, and manual one-line judgments are stable and traceable.
