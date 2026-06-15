from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable


class SnapshotRegressionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SnapshotMetadata:
    path: Path
    sample_count: int
    generated_at: datetime | None


def guard_public_snapshot(candidate_path: str | Path, baseline_paths: Iterable[str | Path]) -> SnapshotMetadata:
    candidate = load_snapshot_metadata(candidate_path)
    baselines = [load_snapshot_metadata(path) for path in baseline_paths if Path(path).exists()]
    if not baselines:
        return candidate

    largest_baseline = max(baselines, key=lambda item: item.sample_count)
    if candidate.sample_count < largest_baseline.sample_count:
        raise SnapshotRegressionError(
            f"candidate snapshot has fewer samples ({candidate.sample_count}) than published baseline "
            f"({largest_baseline.sample_count}) at {largest_baseline.path}"
        )

    dated_baselines = [item for item in baselines if item.generated_at is not None]
    if candidate.generated_at is not None and dated_baselines:
        newest_baseline = max(dated_baselines, key=lambda item: item.generated_at or datetime.min.replace(tzinfo=timezone.utc))
        if candidate.generated_at < newest_baseline.generated_at:
            raise SnapshotRegressionError(
                f"candidate snapshot is older ({candidate.generated_at.isoformat()}) than published baseline "
                f"({newest_baseline.generated_at.isoformat()}) at {newest_baseline.path}"
            )

    return candidate


def load_snapshot_metadata(path: str | Path) -> SnapshotMetadata:
    snapshot_path = Path(path)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    samples = payload.get("samples")
    if samples is None:
        samples = payload.get("videos")
    if not isinstance(samples, list):
        raise SnapshotRegressionError(f"snapshot missing samples list: {snapshot_path}")
    return SnapshotMetadata(
        path=snapshot_path,
        sample_count=len(samples),
        generated_at=_parse_datetime(payload.get("generatedAt") or payload.get("generated_at")),
    )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
