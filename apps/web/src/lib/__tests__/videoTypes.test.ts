import { describe, expect, it } from "vitest";
import { buildVideoTypeFacets, getVideoType, OTHER_TYPE, VIDEO_TYPE_ORDER } from "../videoTypes";
import { filterAndSortSamples } from "../search";
import type { Sample } from "../../types";

function sample(overrides: Partial<Sample>): Sample {
  return {
    id: 1,
    platform: "bilibili",
    creator: { name: "先看评测", tags: ["数码科技", "评测"], note: "评测类封标参考" },
    videoId: "BV1",
    title: "",
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
      followerCount: 1000,
    },
    cover: { url: "/covers/1.jpg", sourceUrl: "https://example.com/1.jpg" },
    card: {
      track: "",
      humanNote: "",
      status: "auto",
      baselinePlayCount: 1000,
      relativeToBaseline: 1.2,
      viewsPerFollower: 3,
    },
    ...overrides,
  };
}

describe("getVideoType — keyword categorization", () => {
  const cases: Array<[string, string]> = [
    ["荣耀Magic V2 拆解评测：这就是折叠屏压缩指南", "手机"],
    ["麒麟 5G 确认回归实测，华为 Mate 60 Pro 拆解", "手机"],
    ["星闪平板能打吗？华为 MatePad Pro 13.2'' 评测", "平板"],
    ["一万块钱买个iPad mini，没想到……", "平板"],
    ["百元入门吊打索尼旗舰？入门耳机到底怎么选?", "耳机"],
    ["在东京听《渡口》，索尼 WF-1000XM5 降噪效果有多强？", "耳机"],
    ["9999 元的百寸电视值得买吗？小米大屏电视选购指南", "电视"],
    ["万元光机拆给你看！极米 RS 10 Ultra 投影仪评测", "电视"],
    ["油烟机推荐！300 块和 6000 块油烟机大 PK", "智能家居"],
    ["深入拆解 10 把智能锁！如何买锁才能安心“入门”？", "智能家居"],
    ["全面对比！五款热门人体工学椅，哪款更值得买？", "人体工学椅"],
    ["如何上班按摩不被领导发现？西昊 T6 上「腚」评测", "人体工学椅"],
    ["数码宝贝进车圈，差点就翻车了？理想 MEGA 实测", "汽车"],
    ["泡水车都去哪了？揭秘二手车内幕 | 车主报告 EP5 上集", "汽车"],
    ["iOS 27 体验：国行这次参与感不太够", "系统"],
    ["苹果 AI 大更新？库克 WWDC 2026 演讲五大升级盘点", "系统"],
    ["2026年，我到底该买哪台相机？", "相机评测"],
    ["全景相机+无人机=无限运镜可能?Insta360 的新航拍方案", "相机评测"],
    ["和李现，一起攀登雪山", "出行旅游"],
    ["租 IMAX 影院！对比AR 眼镜，差距有多大？| 雷鸟GT MAX观影眼镜体验", "眼镜"],
    ["关于智能眼镜的地铁小故事", "眼镜"],
    ["新地图解锁！影视飓风的电竞房？", "Roomtour"],
  ];

  it.each(cases)("categorizes %s -> %s", (title, expected) => {
    expect(getVideoType(sample({ title }))).toBe(expected);
  });

  it("falls back to 其他 when nothing matches", () => {
    expect(getVideoType(sample({ title: "一个视频卖到 1600 万，我们是怎么做到的？" }))).toBe(OTHER_TYPE);
    expect(getVideoType(sample({ title: "假如评测博主说真话，两小时全程高能" }))).toBe(OTHER_TYPE);
  });
});

describe("getVideoType — tie breaks resolve to the more specific type", () => {
  it("prefers 手机 over 相机评测 for a phone with a camera angle", () => {
    expect(getVideoType(sample({ title: "用客观数据给长焦排个名！vivo X100 系列深度评测" }))).toBe("手机");
  });

  it("prefers 平板 over 系统 for a tablet that mentions an OS", () => {
    expect(getVideoType(sample({ title: "远程操控 macOS！搭载天玑 9300 的 vivo Pad3 Pro 值得买吗？" }))).toBe("平板");
  });

  it("prefers 人体工学椅 over 汽车 for car-seat wording", () => {
    expect(getVideoType(sample({ title: "耗资百万搬回飞机高铁汽车座椅？三大高端座椅真实盲测" }))).toBe("人体工学椅");
  });

  it("does not let an incidental 特斯拉 mention pull a robot vacuum into 汽车", () => {
    expect(getVideoType(sample({ title: "特斯拉同款视觉识别，能扫多干净？云鲸逍遥 001 对比评测" }))).toBe("智能家居");
  });
});

describe("getVideoType — uses secondary signals when title is thin", () => {
  it("reads creator tags / track / notes, not just the title", () => {
    const fromTrack = sample({ title: "新品上手", card: { ...sample({}).card, track: "智能眼镜" } });
    expect(getVideoType(fromTrack)).toBe("眼镜");
  });
});

describe("buildVideoTypeFacets", () => {
  it("returns every nav type in display order with counts that sum to the input", () => {
    const samples = [
      sample({ id: 1, title: "华为 Mate 60 Pro 拆解" }),
      sample({ id: 2, title: "人体工学椅选购指南" }),
      sample({ id: 3, title: "随便聊聊" }),
    ];
    const facets = buildVideoTypeFacets(samples);

    expect(facets.map((facet) => facet.value)).toEqual(VIDEO_TYPE_ORDER);
    expect(facets.reduce((sum, facet) => sum + facet.count, 0)).toBe(samples.length);
    expect(facets.find((facet) => facet.value === "手机")?.count).toBe(1);
    expect(facets.find((facet) => facet.value === "人体工学椅")?.count).toBe(1);
    expect(facets.find((facet) => facet.value === OTHER_TYPE)?.count).toBe(1);
  });
});

describe("filterAndSortSamples — video type selection", () => {
  const samples = [
    sample({ id: 1, title: "华为 Mate 60 Pro 拆解评测" }),
    sample({ id: 2, title: "人体工学椅选购指南" }),
    sample({ id: 3, title: "iPad mini 体验" }),
  ];

  it("keeps only samples of the selected type", () => {
    const result = filterAndSortSamples(samples, {
      query: "",
      filters: { platforms: [], creators: [], tags: [], buckets: [] },
      sort: "recent",
      videoType: "手机",
    });
    expect(result.map((item) => item.id)).toEqual([1]);
  });

  it("returns everything when no type is selected", () => {
    const result = filterAndSortSamples(samples, {
      query: "",
      filters: { platforms: [], creators: [], tags: [], buckets: [] },
      sort: "recent",
      videoType: null,
    });
    expect(result.map((item) => item.id).sort()).toEqual([1, 2, 3]);
  });
});
