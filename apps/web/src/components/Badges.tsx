import { getPerformanceBucket } from "../lib/buckets";
import { formatRatio } from "../lib/format";
import type { Sample } from "../types";

export function PlatformBadge({ platform }: { platform: string }) {
  return <span className={`platform-tag ${platform.toLowerCase()}`}>{platformLabel(platform)}</span>;
}

export function PerformanceBadge({ sample }: { sample: Sample }) {
  const bucket = getPerformanceBucket(sample.card.relativeToBaseline);
  return (
    <span
      className={`perf-tag ${bucket.tone}`}
      title="库内相对表现基于该创作者当前样本的中位数，不是严格同期对比。"
    >
      <span className="perf-dot" aria-hidden="true" />
      {bucket.shortLabel}
      <span className="perf-ratio">{formatRatio(sample.card.relativeToBaseline)}</span>
    </span>
  );
}

export function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) {
    return null;
  }
  return (
    <div className="tag-list">
      {tags.map((tag) => (
        <span className="tag" key={tag}>
          {tag}
        </span>
      ))}
    </div>
  );
}

function platformLabel(platform: string): string {
  if (platform === "bilibili") {
    return "B站";
  }
  if (platform === "youtube") {
    return "YouTube";
  }
  return platform;
}
