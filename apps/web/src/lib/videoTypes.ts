import { normalizeText } from "./text";
import type { Sample } from "../types";

/**
 * Frontend-only video-type categorizer.
 *
 * The snapshot has no backend category field (card.track / card.humanNote are
 * currently empty in the data), so we infer a single "video type" per sample
 * from its title plus the lighter signals (creator tags / notes).
 *
 * Design goals from the brief:
 * - deterministic (no randomness, stable ordering)
 * - testable (pure functions, exported rules)
 * - easy to adjust (rules are plain keyword lists)
 *
 * How it works:
 * - Each type has a list of lowercase keywords. For a sample we build a small
 *   weighted haystack (title weighs more than tags/notes) and count keyword
 *   hits per type.
 * - The highest-scoring type wins. Ties are broken by MATCH_PRIORITY, which is
 *   ordered most-specific first (a chair brand beats the broad "smart home"
 *   bucket, a phone model beats a generic "camera" mention, etc.).
 * - No hit at all falls back to `其他`.
 */

export const OTHER_TYPE = "其他";

/** Display order for the left navigation (matches the product brief exactly). */
export const VIDEO_TYPE_ORDER: string[] = [
  "手机",
  "平板",
  "耳机",
  "电视",
  "智能家居",
  "人体工学椅",
  "DIY",
  "汽车",
  "系统",
  "相机评测",
  "出行旅游",
  "眼镜",
  "Roomtour",
  OTHER_TYPE,
];

interface TypeRule {
  id: string;
  keywords: string[];
}

/**
 * Keyword rules. Keywords are matched as normalized (lowercased, fullwidth-folded)
 * substrings, so Latin model names must be lowercase here. Prefer concrete product
 * nouns / model families over bare brand names, because most brands span several
 * product lines (雷鸟 = TVs *and* glasses, 大疆 = drones *and* robot vacuums, 西昊 =
 * chairs). Concrete nouns keep the categorizer stable.
 */
const RULES: TypeRule[] = [
  {
    id: "人体工学椅",
    keywords: [
      "人体工学椅",
      "工学椅",
      "电竞椅",
      "椅子",
      "座椅",
      "腰托",
      "腰枕",
      "撑腰",
      "网椅",
      "西昊",
      "永艺",
      "保友",
      "清闲",
      "把椅",
    ],
  },
  {
    id: "眼镜",
    keywords: ["智能眼镜", "观影眼镜", "ar 眼镜", "ar眼镜", "眼镜", "智能镜"],
  },
  {
    id: "Roomtour",
    keywords: ["roomtour", "room tour", "电竞房", "工作室", "桌搭", "桌面搭建", "书房", "我的房间"],
  },
  {
    id: "汽车",
    keywords: [
      "车主报告",
      "车机",
      "买车",
      "提车",
      "二手车",
      "电车",
      "新能源车",
      "轿车",
      "suv",
      "悬架",
      "理想",
      "问界",
      "小鹏",
      "智界",
      "极氪",
      "零跑",
      "享界",
      "领克",
      "鸿蒙智行",
      // Xiaomi car model is only ever written as "yu7" per project rules.
      "yu7",
      "mega",
      "汽车",
    ],
  },
  {
    id: "平板",
    keywords: ["平板", "ipad", "matepad", "pad pro", "pad3", "pad 3", "学习机", "办公本", "tablet"],
  },
  {
    id: "手机",
    keywords: [
      "手机",
      "iphone",
      "smartphone",
      "千元机",
      "折叠屏",
      "折叠机",
      "麒麟",
      "mate 60",
      "mate60",
      "mate 70",
      "mate70",
      "mate 80",
      "mate80",
      "mate x",
      "mate xt",
      "magic v",
      "magic6",
      "magic 6",
      "magic8",
      "magic 8",
      "nova ",
      "pura",
      "find x",
      "x fold",
      "z fold",
      "pocket 2",
      "xperia",
      "x100",
      "x200",
      "17 pro",
      "17pro",
    ],
  },
  {
    id: "耳机",
    keywords: [
      "耳机",
      "降噪",
      "freebuds",
      "airpods",
      "earbuds",
      "降噪豆",
      "wf-1000",
      "入门耳机",
      "入耳",
      "空间音频",
      "耳道",
      "bose",
    ],
  },
  {
    id: "相机评测",
    keywords: [
      "相机",
      "摄影",
      "镜头",
      "长焦",
      "哈苏",
      "无人机",
      "航拍",
      "全景相机",
      "insta360",
      "拇指相机",
      "运镜",
      "pocket 4",
      "尼康",
      "佳能",
      "camera",
    ],
  },
  {
    id: "电视",
    keywords: [
      "电视",
      "显示器",
      "投影",
      "智慧屏",
      "巨幕",
      "彩监",
      "面板",
      "英寸",
      "oled",
      "miniled",
      "mini led",
      "家庭影院",
      "影院",
      "音箱",
      "杜比",
      "全景声",
      "true rgb",
      "裸眼 3d",
      "壁纸电视",
      "matetv",
      "光机",
      "移轴",
    ],
  },
  {
    id: "智能家居",
    keywords: [
      "空调",
      "油烟机",
      "洗衣机",
      "扫地机",
      "扫拖",
      "净水器",
      "按摩仪",
      "吸顶灯",
      "智能锁",
      "牙刷",
      "洗地机",
      "热水器",
      "净化器",
      "路由器",
      "中央空调",
      "大路灯",
      "灯具",
      "吊灯",
      "台灯",
      "剃须刀",
      "吹风机",
      "机器保姆",
      "智能家居",
      "鸿蒙智家",
      "云鲸",
      "石头 g20",
      "追觅",
      "添可",
      "徕芬",
      "飞科",
      "romo",
      "智能家电",
    ],
  },
  {
    id: "系统",
    keywords: ["ios", "wwdc", "siri", "windows", "macos", "harmonyos", "操作系统", "系统更新", "车机系统", "语音助手"],
  },
  {
    id: "出行旅游",
    keywords: ["旅游", "旅行", "自驾", "环游", "雪山", "攀登", "露营", "徒步", "旅程", "vlog"],
  },
  {
    id: "DIY",
    keywords: ["3d打印", "3d 打印", "diy", "别墅", "建模还原", "自制", "手工", "翻新", "改装"],
  },
];

/**
 * Tie-break order when two types score equally. Earlier = wins.
 * Most-specific buckets first so a chair brand beats "smart home", a phone model
 * beats a generic "camera"/"system" mention, a tablet beats a phone, etc.
 */
const MATCH_PRIORITY: string[] = [
  "人体工学椅",
  "眼镜",
  "Roomtour",
  "汽车",
  "平板",
  "手机",
  "耳机",
  "相机评测",
  "电视",
  "智能家居",
  "系统",
  "出行旅游",
  "DIY",
];

const RULE_BY_ID = new Map(RULES.map((rule) => [rule.id, rule]));

function countHits(keywords: string[], title: string, secondary: string): number {
  let score = 0;
  for (const keyword of keywords) {
    if (!keyword) {
      continue;
    }
    if (title.includes(keyword)) {
      // Title is the strongest signal; weight it above tags/notes.
      score += 2;
    } else if (secondary.includes(keyword)) {
      score += 1;
    }
  }
  return score;
}

/**
 * Core categorizer: pick the best-scoring type for an already-normalized title +
 * secondary haystack. Returns `OTHER_TYPE` when nothing matches.
 *
 * Walks in priority order so the first type to reach a given max score keeps it
 * (i.e. ties resolve to the more specific bucket).
 */
function classify(title: string, secondary: string): string {
  let bestType = OTHER_TYPE;
  let bestScore = 0;

  for (const id of MATCH_PRIORITY) {
    const rule = RULE_BY_ID.get(id);
    if (!rule) {
      continue;
    }
    const score = countHits(rule.keywords, title, secondary);
    if (score > bestScore) {
      bestScore = score;
      bestType = id;
    }
  }

  return bestScore > 0 ? bestType : OTHER_TYPE;
}

/**
 * Resolve the single video type for a sample. Deterministic and side-effect free.
 */
export function getVideoType(sample: Sample): string {
  const title = normalizeText(sample.title ?? "");
  const secondary = normalizeText(
    [
      sample.creator?.tags?.join(" ") ?? "",
      sample.creator?.note ?? "",
      sample.card?.track ?? "",
      sample.card?.humanNote ?? "",
    ].join(" "),
  );

  return classify(title, secondary);
}

/**
 * Infer the product type a free-text query/topic is about, using the same
 * keyword rules as `getVideoType`. Returns `null` when the query matches no
 * rule, so generic queries (科技/评测/数码…) don't get a spurious type signal.
 *
 * The search scorer uses this to narrow idea searches ("智能眼镜" → 眼镜,
 * "iPhone 选题" → 手机) instead of expanding into broad category tokens.
 */
export function inferVideoTypeFromText(text: string): string | null {
  const type = classify(normalizeText(text), "");
  return type === OTHER_TYPE ? null : type;
}

export interface VideoTypeFacet {
  value: string;
  label: string;
  count: number;
}

/**
 * Count samples per video type, returned in nav display order. Types with zero
 * samples are still included so the navigation stays stable and predictable.
 */
export function buildVideoTypeFacets(samples: Sample[]): VideoTypeFacet[] {
  const counts = new Map<string, number>();
  for (const id of VIDEO_TYPE_ORDER) {
    counts.set(id, 0);
  }
  for (const sample of samples) {
    const type = getVideoType(sample);
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return VIDEO_TYPE_ORDER.map((id) => ({ value: id, label: id, count: counts.get(id) ?? 0 }));
}
