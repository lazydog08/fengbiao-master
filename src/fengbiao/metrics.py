from __future__ import annotations

from datetime import datetime
from statistics import median


def compute_relative_metrics(
    play_count: int | None,
    creator_recent_play_counts: list[int],
    follower_count: int | None,
) -> dict[str, float | None]:
    clean_counts = [count for count in creator_recent_play_counts if count is not None and count > 0]
    baseline = float(median(clean_counts)) if clean_counts and play_count is not None else None
    relative = round(play_count / baseline, 4) if baseline else None
    views_per_follower = round(play_count / follower_count, 6) if play_count is not None and follower_count else None
    return {
        "baseline_play_count": baseline,
        "relative_to_baseline": relative,
        "views_per_follower": views_per_follower,
    }


def compute_early_growth_per_hour(snapshots: list[tuple[datetime, int]]) -> float | None:
    valid = sorted((ts, count) for ts, count in snapshots if ts and count is not None)
    if len(valid) < 2:
        return None
    first_ts, first_count = valid[0]
    last_ts, last_count = valid[-1]
    hours = (last_ts - first_ts).total_seconds() / 3600
    if hours <= 0:
        return None
    return round((last_count - first_count) / hours, 4)
