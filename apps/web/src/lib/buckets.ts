import type { PerformanceBucketId } from "../types";

export interface PerformanceBucket {
  id: PerformanceBucketId;
  label: string;
  shortLabel: string;
  tone: "hot" | "steady" | "low" | "unknown";
  description: string;
}

const BUCKETS: Record<PerformanceBucketId, PerformanceBucket> = {
  high: {
    id: "high",
    label: "库内高于基线",
    shortLabel: "高表现",
    tone: "hot",
    description: "高于该创作者当前样本的库内中位基线",
  },
  steady: {
    id: "steady",
    label: "接近库内基线",
    shortLabel: "接近基线",
    tone: "steady",
    description: "接近该创作者当前样本的库内中位基线",
  },
  low: {
    id: "low",
    label: "低于库内基线",
    shortLabel: "低表现",
    tone: "low",
    description: "低于该创作者当前样本的库内中位基线",
  },
  unknown: {
    id: "unknown",
    label: "暂无相对表现",
    shortLabel: "暂无数据",
    tone: "unknown",
    description: "当前样本没有足够播放量或基线数据",
  },
};

export function getPerformanceBucket(relativeToBaseline: number | null | undefined): PerformanceBucket {
  if (relativeToBaseline == null || Number.isNaN(relativeToBaseline)) {
    return BUCKETS.unknown;
  }
  if (relativeToBaseline >= 1.5) {
    return BUCKETS.high;
  }
  if (relativeToBaseline >= 0.6) {
    return BUCKETS.steady;
  }
  return BUCKETS.low;
}

export function allPerformanceBuckets(): PerformanceBucket[] {
  return [BUCKETS.high, BUCKETS.steady, BUCKETS.low, BUCKETS.unknown];
}
