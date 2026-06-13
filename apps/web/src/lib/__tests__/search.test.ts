import { describe, expect, it } from "vitest";
import { getPerformanceBucket } from "../buckets";
import { filterAndSortSamples, scoreSample } from "../search";
import type { Sample } from "../../types";

function sample(overrides: Partial<Sample>): Sample {
  return {
    id: 1,
    platform: "bilibili",
    creator: { name: "懒狗小黑", tags: ["科技评测"], note: "别墅 DIY 和智能眼镜都常看" },
    videoId: "BV1",
    title: "智能眼镜这次真能当主力屏幕吗？",
    url: "https://example.com",
    publishedAt: "2026-06-01T00:00:00+00:00",
    firstSeenAt: "2026-06-01T00:00:00+00:00",
    lastSeenAt: "2026-06-03T00:00:00+00:00",
    metrics: {
      playCount: 3000,
      likeCount: 200,
      coinCount: 30,
      favoriteCount: 80,
      danmakuCount: 12,
      followerCount: 1000
    },
    cover: { url: "/covers/1.jpg", sourceUrl: "https://example.com/1.jpg" },
    card: {
      track: "智能眼镜",
      humanNote: "把参数变成真实使用问题",
      status: "auto",
      baselinePlayCount: 1000,
      relativeToBaseline: 3,
      viewsPerFollower: 3
    },
    ...overrides
  };
}

const neutralCard = (): Sample["card"] => ({ ...sample({}).card, track: "", humanNote: "" });

describe("search scoring", () => {
  it("matches natural topic ideas with filler words and mixed iPhone casing", () => {
    const iphone = sample({
      title: "Apple was late on AI, but iPhone users finally get the useful part",
      creator: { name: "Linus Tech Tips", tags: ["tech", "hardware"], note: "" },
      card: neutralCard(),
    });

    expect(scoreSample(iphone, "想做一期 iPhone 选题")).toBeGreaterThan(0);
    expect(scoreSample(iphone, "想做一期 ｉＰｈｏｎｅ 选题")).toBeGreaterThan(0);
  });

  it("searches title, creator, platform, tags, notes, track, and derived metric labels", () => {
    const glasses = sample({});

    expect(scoreSample(glasses, "智能眼镜")).toBeGreaterThan(0);
    expect(scoreSample(glasses, "别墅 DIY")).toBeGreaterThan(0);
    expect(scoreSample(glasses, "库内高于基线")).toBeGreaterThan(0);
  });

  it("narrows an idea search to the related video type even without a literal title match", () => {
    // A glasses video that never spells out 智能眼镜 still scores via type inference.
    const arGlasses = sample({
      title: "雷鸟 GT MAX 观影眼镜，租 IMAX 影院来对比",
      creator: { name: "懒狗小黑", tags: ["科技评测"], note: "" },
      card: neutralCard(),
    });

    expect(scoreSample(arGlasses, "智能眼镜")).toBeGreaterThan(0);
  });

  it("expands iPhone to Apple/苹果 but not into generic tech", () => {
    const apple = sample({
      title: "Apple 这次的影像升级到底值不值",
      creator: { name: "MKBHD", tags: ["review"], note: "" },
      card: neutralCard(),
    });
    const genericTech = sample({
      title: "年度数码好物盘点，这些都值得入手",
      creator: { name: "某科技 up", tags: ["科技评测", "数码"], note: "科技评测与硬件体验参考" },
      card: neutralCard(),
    });

    expect(scoreSample(apple, "想做一期 iPhone 选题")).toBeGreaterThan(0);
    expect(scoreSample(genericTech, "想做一期 iPhone 选题")).toBe(0);
  });

  it("does not let broad words turn idea searches into a whole-library match", () => {
    // Guard against the old behavior: expanding 科技/硬件/体验/review matched
    // almost every creator tag and note, so unrelated tech scored on every idea.
    const genericTech = sample({
      title: "年度数码好物盘点，这些都值得入手",
      creator: { name: "某科技 up", tags: ["科技评测", "数码", "硬件"], note: "科技评测与硬件体验参考" },
      card: neutralCard(),
    });

    expect(scoreSample(genericTech, "智能眼镜")).toBe(0);
    expect(scoreSample(genericTech, "3D 打印")).toBe(0);
    expect(scoreSample(genericTech, "别墅 DIY")).toBe(0);
  });
});

describe("idea-search relevance stays narrow", () => {
  const library = [
    sample({ id: 1, title: "雷鸟 GT MAX 观影眼镜上手", creator: { name: "懒狗小黑", tags: ["科技评测"], note: "" }, card: neutralCard() }),
    sample({ id: 2, title: "iPhone 17 Pro 影像深度评测", creator: { name: "极客湾", tags: ["数码"], note: "" }, card: neutralCard() }),
    sample({ id: 3, title: "年度数码好物盘点，这些都值得入手", creator: { name: "某科技 up", tags: ["科技评测", "数码", "硬件"], note: "科技评测与硬件体验参考" }, card: neutralCard() }),
    sample({ id: 4, title: "9999 元的百寸电视值得买吗", creator: { name: "先看评测", tags: ["数码"], note: "" }, card: neutralCard() }),
  ];

  function ids(query: string): number[] {
    return filterAndSortSamples(library, {
      query,
      filters: { platforms: [], creators: [], tags: [], buckets: [] },
      sort: "relative",
    }).map((item) => item.id);
  }

  it("returns glasses for a 智能眼镜 idea, not the whole library", () => {
    expect(ids("智能眼镜")).toEqual([1]);
  });

  it("prefers phone/Apple samples for an iPhone idea", () => {
    expect(ids("想做一期 iPhone 选题")).toEqual([2]);
  });

  it("does not treat an iPhone query as every phone sample", () => {
    const phoneLibrary = [
      sample({ id: 1, title: "iPhone 17 Pro 影像深度评测", creator: { name: "极客湾", tags: ["数码"], note: "" }, card: neutralCard() }),
      sample({ id: 2, title: "Apple 这次的影像升级到底值不值", creator: { name: "MKBHD", tags: ["review"], note: "" }, card: neutralCard() }),
      sample({ id: 3, title: "华为 Pura 80 Ultra 影像评测", creator: { name: "先看评测", tags: ["数码"], note: "" }, card: neutralCard() }),
      sample({ id: 4, title: "荣耀 Magic V2 拆解评测", creator: { name: "爱玩的建钢", tags: ["数码"], note: "" }, card: neutralCard() }),
      sample({ id: 5, title: "华为 Pura 80 Ultra 一挑三？对比 iPhone、OPPO、vivo 影像超大杯", creator: { name: "先看评测", tags: ["数码"], note: "" }, card: neutralCard() }),
    ];

    const result = filterAndSortSamples(phoneLibrary, {
      query: "想做一期 iPhone 选题",
      filters: { platforms: [], creators: [], tags: [], buckets: [] },
      sort: "relative",
    }).map((item) => item.id);

    expect(result).toEqual([1, 2]);
  });
});

describe("filters and sorting", () => {
  it("applies AND between filter groups and OR within each group", () => {
    const samples = [
      sample({ id: 1, creator: { name: "懒狗小黑", tags: ["科技评测"], note: "" } }),
      sample({ id: 2, creator: { name: "MKBHD", tags: ["tech"], note: "" }, platform: "youtube" }),
      sample({ id: 3, creator: { name: "极客湾", tags: ["硬件"], note: "" } })
    ];

    const result = filterAndSortSamples(samples, {
      query: "",
      filters: { platforms: ["bilibili"], creators: [], tags: ["科技评测", "硬件"], buckets: [] },
      sort: "recent"
    });

    expect(result.map((item) => item.id)).toEqual([1, 3]);
  });

  it("sorts null metrics after real values", () => {
    const samples = [
      sample({ id: 1, metrics: { ...sample({}).metrics, playCount: null }, card: { ...sample({}).card, relativeToBaseline: null } }),
      sample({ id: 2, metrics: { ...sample({}).metrics, playCount: 5000 }, card: { ...sample({}).card, relativeToBaseline: 1.2 } })
    ];

    expect(
      filterAndSortSamples(samples, {
        query: "",
        filters: { platforms: [], creators: [], tags: [], buckets: [] },
        sort: "play"
      }).map((item) => item.id)
    ).toEqual([2, 1]);
    expect(
      filterAndSortSamples(samples, {
        query: "",
        filters: { platforms: [], creators: [], tags: [], buckets: [] },
        sort: "relative"
      }).map((item) => item.id)
    ).toEqual([2, 1]);
  });

  it("keeps invalid recent dates behind valid dates", () => {
    const samples = [
      sample({ id: 1, lastSeenAt: "not-a-date" }),
      sample({ id: 2, lastSeenAt: "2026-06-05T00:00:00+00:00" }),
    ];

    expect(
      filterAndSortSamples(samples, {
        query: "",
        filters: { platforms: [], creators: [], tags: [], buckets: [] },
        sort: "recent"
      }).map((item) => item.id)
    ).toEqual([2, 1]);
  });
});

describe("performance buckets", () => {
  it("labels high, normal, low, and unknown library-relative performance", () => {
    expect(getPerformanceBucket(2.2).id).toBe("high");
    expect(getPerformanceBucket(0.8).id).toBe("steady");
    expect(getPerformanceBucket(0.35).id).toBe("low");
    expect(getPerformanceBucket(null).id).toBe("unknown");
  });
});
