import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DetailDrawer } from "./DetailDrawer";
import type { Sample } from "../types";

const sample: Sample = {
  id: 1,
  platform: "bilibili",
  creator: { name: "懒狗小黑", tags: ["科技评测"] },
  videoId: "BV1",
  title: "智能眼镜这次能当主力屏幕吗？",
  url: "https://www.bilibili.com/video/BV1",
  publishedAt: null,
  firstSeenAt: "2026-06-14T00:00:00+00:00",
  lastSeenAt: "2026-06-14T00:00:00+00:00",
  metrics: {
    playCount: 100,
    likeCount: null,
    coinCount: null,
    favoriteCount: null,
    danmakuCount: null,
    followerCount: null
  },
  cover: { url: "/covers/1.jpg" },
  card: {
    track: "",
    humanNote: "人工判断优先展示",
    status: "",
    baselinePlayCount: 80,
    relativeToBaseline: 1.25,
    viewsPerFollower: null
  },
  analysis: {
    version: 1,
    generated_at: "2026-06-14T00:00:00+00:00",
    source: "rule",
    performance: {
      bucket: "steady",
      relative_to_baseline: 1.25,
      confidence: "low",
      basis: "relative-to-creator-baseline"
    },
    title: {
      char_len: 15,
      features: [
        { id: "question", label: "疑问句式", present: true },
        { id: "number", label: "含具体数字", present: false }
      ]
    },
    cover: {
      has_asset: true,
      width: 1280,
      height: 720,
      aspect_ratio: 1.778,
      orientation: "landscape",
      cover_changed: false,
      title_changed: true
    },
    explanation: {
      structure: "标题是疑问结构，封面为横版构图。",
      features: "可见特征集中在疑问句式。",
      interpretation: "这个样本接近该创作者库内基线。"
    },
    caveats: ["本判断基于库内相对表现，不代表真实点击率。"]
  }
};

describe("DetailDrawer", () => {
  it("renders structured rule analysis when available", () => {
    const html = renderToStaticMarkup(
      <DetailDrawer
        sample={sample}
        favorite={false}
        onClose={vi.fn()}
        onToggleFavorite={vi.fn()}
      />,
    );

    expect(html).toContain("封标结构");
    expect(html).toContain("特征");
    expect(html).toContain("表现判断");
    expect(html).toContain("为什么可能");
    expect(html).toContain("疑问句式");
    expect(html).toContain("数据不足，仅供参考");
    expect(html).toContain("人工备注");
    expect(html).toContain("人工判断优先展示");
    const sourceLink = extractSourceLink(html);
    expect(sourceLink).toContain("<span>打开原视频</span>");
    expect(sourceLink).toContain('class="drawer-source-link"');
    expect(sourceLink).toContain('href="https://www.bilibili.com/video/BV1"');
    expect(sourceLink).toContain('target="_blank"');
    expect(sourceLink).toContain('rel="noreferrer"');
    expect(sourceLink).toContain('class="sr-only"');
    expect(html).toContain('aria-label="快捷打开原视频，新标签页打开"');
  });

  it("keeps rendering core details when analysis is partial or invalid", () => {
    const damagedSample: Sample = {
      ...sample,
      analysis: {
        version: 2,
        performance: { confidence: "low" },
        explanation: { structure: "半截结构说明" },
      } as unknown as Sample["analysis"],
    };

    let html = "";
    expect(() => {
      html = renderToStaticMarkup(
        <DetailDrawer
          sample={damagedSample}
          favorite={false}
          onClose={vi.fn()}
          onToggleFavorite={vi.fn()}
        />,
      );
    }).not.toThrow();

    expect(html).toContain("人工备注");
    expect(html).toContain("人工判断优先展示");
    expect(html).toContain("收录信息");
    expect(html).toContain("智能眼镜这次能当主力屏幕吗？");
  });

  it("hides original-video links when the sample url is empty", () => {
    const sampleWithoutUrl: Sample = { ...sample, url: "" };

    const html = renderToStaticMarkup(
      <DetailDrawer
        sample={sampleWithoutUrl}
        favorite={false}
        onClose={vi.fn()}
        onToggleFavorite={vi.fn()}
      />,
    );

    expect(html).not.toContain('class="drawer-source-link"');
    expect(html).not.toContain('href=""');
    expect(html).toContain("智能眼镜这次能当主力屏幕吗？");
  });

  it("hides original-video links when the sample url uses an unsafe scheme", () => {
    const sampleWithUnsafeUrl: Sample = { ...sample, url: "javascript:alert(1)" };

    const html = renderToStaticMarkup(
      <DetailDrawer
        sample={sampleWithUnsafeUrl}
        favorite={false}
        onClose={vi.fn()}
        onToggleFavorite={vi.fn()}
      />,
    );

    expect(html).not.toContain('class="drawer-source-link"');
    expect(html).not.toContain("javascript:alert");
    expect(html).toContain("智能眼镜这次能当主力屏幕吗？");
  });
});

function extractSourceLink(html: string): string {
  const match = html.match(/<a class="drawer-source-link"[^>]*>.*?<\/a>/);
  expect(match).not.toBeNull();
  return match?.[0] ?? "";
}
