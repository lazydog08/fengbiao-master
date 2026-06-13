import { getPerformanceBucket } from "./buckets";
import { getVideoType } from "./videoTypes";
import { normalizeText } from "./text";
import type { LibraryQuery, Sample, SortKey } from "../types";

type WeightedField = [string, number];

// Conversational scaffolding people type around a topic ("想做一期 … 选题") that
// carries no matchable meaning and would otherwise match noise.
const TOKEN_FILLERS = new Set([
  "想做一期",
  "想做",
  "一期",
  "选题",
  "视频",
  "做",
  "一个",
  "关于",
  "想",
  "拍",
]);

/**
 * Tight brand-equivalence synonyms ONLY.
 *
 * These must stay narrow (brand / product nouns), never broad category words
 * like 科技 / 硬件 / 评测 / 数码 / review — broad tokens match generic creator
 * tags and notes, which is exactly what turned every idea search into a
 * whole-library search. Product-type narrowing is handled separately and only
 * for category-style queries, not brand/model names.
 */
const INTENT_SYNONYMS: Array<[string, string[]]> = [
  ["iphone", ["apple"]],
  ["apple", ["iphone", "苹果"]],
  ["苹果", ["iphone", "apple"]],
];

// Exact (typed) query tokens dominate. The strongest signals are the title and
// the creator name; tags / notes are softer so a single broad note word can't
// outweigh a real title hit.
const FIELD_WEIGHTS = {
  title: 12,
  videoType: 9,
  creator: 6,
  platform: 3,
  tags: 5,
  note: 4,
  track: 5,
  humanNote: 4,
  bucket: 4,
};

// Synonyms contribute, but at a fraction of an exact hit so they can never
// outrank a sample that literally matches what was typed.
const SYNONYM_WEIGHT_FACTOR = 0.4;

// Bonus when the query clearly implies one product type and the sample is that
// type. This is what makes "智能眼镜" mostly return glasses and "iPhone 选题"
// prefer phones, without dragging in every tech video.
const TYPE_MATCH_BONUS = 14;

const TYPE_QUERY_KEYWORDS: Array<[string, string[]]> = [
  ["手机", ["手机", "折叠屏", "折叠机", "千元机"]],
  ["平板", ["平板", "学习机", "办公本", "tablet"]],
  ["耳机", ["耳机", "降噪", "入耳", "空间音频"]],
  ["电视", ["电视", "显示器", "投影", "家庭影院", "影院"]],
  ["智能家居", ["智能家居", "家电", "扫地机", "扫拖", "空调", "洗衣机", "智能锁"]],
  ["人体工学椅", ["人体工学椅", "工学椅", "电竞椅", "椅子", "座椅"]],
  ["DIY", ["3d打印", "3d 打印", "diy", "别墅", "自制", "手工", "翻新", "改装"]],
  ["汽车", ["汽车", "买车", "提车", "车主报告", "二手车", "电车", "新能源车"]],
  ["系统", ["系统", "操作系统", "系统更新", "ios", "windows", "macos", "harmonyos"]],
  ["相机评测", ["相机", "摄影", "镜头", "无人机", "航拍", "全景相机"]],
  ["出行旅游", ["旅游", "旅行", "自驾", "雪山", "露营", "徒步", "vlog"]],
  ["眼镜", ["智能眼镜", "观影眼镜", "ar眼镜", "ar 眼镜", "眼镜"]],
  ["Roomtour", ["roomtour", "room tour", "桌搭", "电竞房", "工作室", "书房"]],
];

const APPLE_QUERY_TERMS = ["iphone", "apple", "苹果"];
const COMPETING_PHONE_BRANDS = [
  "华为",
  "pura",
  "mate ",
  "oppo",
  "vivo",
  "荣耀",
  "magic",
  "小米",
  "红米",
  "一加",
  "oneplus",
  "三星",
  "galaxy",
  "find x",
  "xperia",
  "iqoo",
  "realme",
];
const COMPARISON_MARKERS = ["对比", "一挑", "横评", "vs", "pk"];

export { normalizeText };

/** Exact tokens the user typed, minus conversational filler. Order-stable, deduped. */
export function queryTokens(query: string): string[] {
  const normalized = stripFillers(normalizeText(query));
  const tokens = normalized
    .split(" ")
    .map((token) => token.trim())
    .filter(Boolean)
    .filter((token) => !TOKEN_FILLERS.has(token));
  return [...new Set(tokens)];
}

function stripFillers(normalizedQuery: string): string {
  let stripped = ` ${normalizedQuery} `;
  for (const filler of TOKEN_FILLERS) {
    stripped = stripped.split(normalizeText(filler)).join(" ");
  }
  return stripped.replace(/\s+/g, " ").trim();
}

function inferCategoryQueryType(query: string): string | null {
  const normalized = stripFillers(normalizeText(query));
  const compact = normalized.replace(/\s+/g, "");
  for (const [type, keywords] of TYPE_QUERY_KEYWORDS) {
    for (const keyword of keywords) {
      const normalizedKeyword = normalizeText(keyword);
      const compactKeyword = normalizedKeyword.replace(/\s+/g, "");
      if (normalized.includes(normalizedKeyword) || compact.includes(compactKeyword)) {
        return type;
      }
    }
  }
  return null;
}

/** Narrow brand synonyms triggered by the query, excluding tokens already typed. */
function synonymTokens(exactTokens: string[], query: string): string[] {
  const compact = normalizeText(query).replace(/\s+/g, "");
  const exactSet = new Set(exactTokens);
  const synonyms = new Set<string>();
  for (const [trigger, additions] of INTENT_SYNONYMS) {
    if (!compact.includes(trigger)) {
      continue;
    }
    for (const addition of additions) {
      const token = normalizeText(addition);
      if (!exactSet.has(token)) {
        synonyms.add(token);
      }
    }
  }
  return [...synonyms];
}

export function scoreSample(sample: Sample, query: string): number {
  const exact = queryTokens(query);
  if (exact.length === 0) {
    return 0;
  }

  if (isAppleFocusedQuery(query) && !isAppleFocusedSample(sample)) {
    return 0;
  }

  const sampleType = getVideoType(sample);
  const fields = sampleFields(sample, sampleType);
  let score = 0;

  for (const token of exact) {
    for (const [field, weight] of fields) {
      if (field.includes(token)) {
        score += weight;
      }
    }
  }

  for (const token of synonymTokens(exact, query)) {
    for (const [field, weight] of fields) {
      if (field.includes(token)) {
        score += weight * SYNONYM_WEIGHT_FACTOR;
      }
    }
  }

  // Type inference is only for category-style ideas ("智能眼镜", "3D 打印",
  // "手机选题"). Brand/model queries such as "iPhone" must not become "all
  // phones", or search stops feeling trustworthy.
  const targetType = inferCategoryQueryType(query);
  if (targetType && sampleType === targetType) {
    score += TYPE_MATCH_BONUS;
  }

  return score;
}

function isAppleFocusedQuery(query: string): boolean {
  const compact = normalizeText(query).replace(/\s+/g, "");
  return APPLE_QUERY_TERMS.some((term) => compact.includes(term));
}

function isAppleFocusedSample(sample: Sample): boolean {
  const title = normalizeText(sample.title);
  const applePositions = APPLE_QUERY_TERMS
    .map((term) => title.indexOf(term))
    .filter((position) => position >= 0);
  if (applePositions.length === 0) {
    return false;
  }

  const firstAppleMention = Math.min(...applePositions);
  const beforeApple = title.slice(0, firstAppleMention);
  const hasCompetingBrandBeforeApple = COMPETING_PHONE_BRANDS.some((brand) => beforeApple.includes(brand));
  const framesAppleAsComparisonTarget = COMPARISON_MARKERS.some((marker) => title.includes(`${marker} iphone`) || beforeApple.includes(marker));

  return !(hasCompetingBrandBeforeApple && framesAppleAsComparisonTarget);
}

export function filterAndSortSamples(samples: Sample[], options: LibraryQuery): Sample[] {
  const scored = samples
    .map((sample) => ({ sample, score: scoreSample(sample, options.query) }))
    .filter(({ sample, score }) => {
      if (options.query.trim() && score <= 0) {
        return false;
      }
      if (options.videoType && getVideoType(sample) !== options.videoType) {
        return false;
      }
      return matchesFilters(sample, options.filters);
    });

  return scored
    .sort((a, b) => {
      if (options.query.trim() && b.score !== a.score) {
        return b.score - a.score;
      }
      return compareBySort(a.sample, b.sample, options.sort);
    })
    .map(({ sample }) => sample);
}

export function compareBySort(a: Sample, b: Sample, sort: SortKey): number {
  if (sort === "play") {
    return compareNullableDesc(a.metrics.playCount, b.metrics.playCount);
  }
  if (sort === "relative") {
    return compareNullableDesc(a.card.relativeToBaseline, b.card.relativeToBaseline);
  }
  return safeTime(b.lastSeenAt) - safeTime(a.lastSeenAt);
}

function matchesFilters(sample: Sample, filters: LibraryQuery["filters"]): boolean {
  if (filters.platforms.length > 0 && !filters.platforms.includes(sample.platform)) {
    return false;
  }
  if (filters.creators.length > 0 && !filters.creators.includes(sample.creator.name)) {
    return false;
  }
  if (filters.tags.length > 0 && !sample.creator.tags.some((tag) => filters.tags.includes(tag))) {
    return false;
  }
  if (filters.buckets.length > 0 && !filters.buckets.includes(getPerformanceBucket(sample.card.relativeToBaseline).id)) {
    return false;
  }
  return true;
}

function compareNullableDesc(a: number | null, b: number | null): number {
  if (a == null && b == null) {
    return 0;
  }
  if (a == null) {
    return 1;
  }
  if (b == null) {
    return -1;
  }
  return b - a;
}

function safeTime(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

function sampleFields(sample: Sample, videoType: string): WeightedField[] {
  const bucket = getPerformanceBucket(sample.card.relativeToBaseline);
  const fields: WeightedField[] = [
    [sample.title, FIELD_WEIGHTS.title],
    // Inferred product type is searchable, so "手机"/"眼镜"/"汽车" match directly.
    [videoType, FIELD_WEIGHTS.videoType],
    [sample.creator.name, FIELD_WEIGHTS.creator],
    [sample.platform, FIELD_WEIGHTS.platform],
    [sample.creator.tags.join(" "), FIELD_WEIGHTS.tags],
    [sample.creator.note ?? "", FIELD_WEIGHTS.note],
    [sample.card.track, FIELD_WEIGHTS.track],
    [sample.card.humanNote, FIELD_WEIGHTS.humanNote],
    [bucket.label, FIELD_WEIGHTS.bucket],
    [bucket.shortLabel, 3],
    [bucket.description, 2],
  ];
  return fields.map(([value, weight]) => [normalizeText(value), weight]);
}
