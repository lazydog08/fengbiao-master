export type SortKey = "recent" | "play" | "relative";

export type PerformanceBucketId = "high" | "steady" | "low" | "unknown";

export interface CreatorInfo {
  name: string;
  tags: string[];
  note: string;
}

export interface SampleMetrics {
  playCount: number | null;
  likeCount: number | null;
  coinCount: number | null;
  favoriteCount: number | null;
  danmakuCount: number | null;
  followerCount: number | null;
}

export interface CoverInfo {
  url: string | null;
  path?: string | null;
  sourceUrl: string | null;
}

export interface SampleCardInfo {
  track: string;
  humanNote: string;
  status: string;
  baselinePlayCount: number | null;
  relativeToBaseline: number | null;
  viewsPerFollower: number | null;
}

export interface Sample {
  id: number;
  platform: string;
  creator: CreatorInfo;
  videoId: string;
  title: string;
  url: string;
  publishedAt: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
  metrics: SampleMetrics;
  cover: CoverInfo;
  card: SampleCardInfo;
}

export interface SnapshotPayload {
  generatedAt: string;
  counts: {
    creators: number;
    videos: number;
    samples: number;
  };
  samples: Sample[];
  notes?: {
    scope?: string;
    relativeMetric?: string;
  };
}

export interface LibraryFilters {
  platforms: string[];
  creators: string[];
  tags: string[];
  buckets: PerformanceBucketId[];
}

export interface LibraryQuery {
  query: string;
  filters: LibraryFilters;
  sort: SortKey;
  /** Primary left-nav selection. `null` means "all video types". */
  videoType?: string | null;
}

export interface FacetOption {
  value: string;
  label: string;
  count: number;
}
