export type SortKey = "recent" | "play" | "relative";

export type PerformanceBucketId = "high" | "steady" | "low" | "unknown";

export interface CreatorInfo {
  name: string;
  tags: string[];
  note?: string;
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
  sourceUrl?: string | null;
}

export interface SampleCardInfo {
  track: string;
  humanNote: string;
  status: string;
  baselinePlayCount: number | null;
  relativeToBaseline: number | null;
  viewsPerFollower: number | null;
}

export interface SampleAnalysisFeature {
  id: string;
  label: string;
  present: boolean;
}

export interface SampleAnalysis {
  version: number;
  generated_at?: string;
  source: string;
  performance: {
    bucket: PerformanceBucketId;
    relative_to_baseline: number | null;
    confidence: "ok" | "low" | string;
    basis: string;
  };
  title: {
    char_len: number;
    features: SampleAnalysisFeature[];
  };
  cover: {
    has_asset: boolean;
    width: number | null;
    height: number | null;
    aspect_ratio: number | null;
    orientation: "landscape" | "portrait" | "square" | "unknown" | string;
    cover_changed: boolean;
    title_changed: boolean;
  };
  explanation: {
    structure: string;
    features: string;
    interpretation: string;
  };
  caveats: string[];
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
  analysis?: SampleAnalysis | null;
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
