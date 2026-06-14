import { describe, expect, it, vi } from "vitest";
import { loadSnapshot, withBasePath } from "./snapshotClient";
import type { SnapshotPayload } from "../types";

function payload(generatedAt: string): SnapshotPayload {
  return {
    generatedAt,
    counts: { creators: 1, videos: 1, samples: 1 },
    samples: []
  };
}

function jsonResponse(body: SnapshotPayload, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body
  } as Response;
}

describe("loadSnapshot", () => {
  it("loads the live backend snapshot before the static file", async () => {
    const apiPayload = payload("2026-06-13T01:00:00+00:00");
    const fetcher = vi.fn().mockResolvedValueOnce(jsonResponse(apiPayload));

    const result = await loadSnapshot(fetcher);

    expect(result.source).toBe("api");
    expect(result.payload).toBe(apiPayload);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith("/api/snapshot", { cache: "no-store" });
  });

  it("falls back to the static snapshot when the backend is unavailable", async () => {
    const staticPayload = payload("2026-06-13T02:00:00+00:00");
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("backend down")).mockResolvedValueOnce(jsonResponse(staticPayload));

    const result = await loadSnapshot(fetcher);

    expect(result.source).toBe("static");
    expect(result.payload).toBe(staticPayload);
    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/snapshot", { cache: "no-store" });
    expect(fetcher).toHaveBeenNthCalledWith(2, "/fengbiao-snapshot.json", { cache: "no-store" });
  });

  it("can force the backend to export a fresh snapshot", async () => {
    const apiPayload = payload("2026-06-13T03:00:00+00:00");
    const fetcher = vi.fn().mockResolvedValueOnce(jsonResponse(apiPayload));

    const result = await loadSnapshot(fetcher, { forceExport: true });

    expect(result.source).toBe("api");
    expect(result.payload).toBe(apiPayload);
    expect(fetcher).toHaveBeenCalledWith("/api/snapshot?export=1", { cache: "no-store" });
  });

  it("can skip the local backend for static hosting", async () => {
    const staticPayload = payload("2026-06-13T04:00:00+00:00");
    const fetcher = vi.fn().mockResolvedValueOnce(jsonResponse(staticPayload));

    const result = await loadSnapshot(fetcher, { preferApi: false });

    expect(result.source).toBe("static");
    expect(result.payload).toBe(staticPayload);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith("/fengbiao-snapshot.json", { cache: "no-store" });
  });

  it("keeps static assets under the configured Vite base path", () => {
    expect(withBasePath("/covers/1.jpg")).toBe("/covers/1.jpg");
    expect(withBasePath("/covers/1.jpg", "/fengbiao-master/")).toBe("/fengbiao-master/covers/1.jpg");
    expect(withBasePath("/fengbiao-snapshot.json", "/fengbiao-master")).toBe("/fengbiao-master/fengbiao-snapshot.json");
    expect(withBasePath("https://example.com/cover.jpg")).toBe("https://example.com/cover.jpg");
  });

  it("accepts samples with and without rule analysis", async () => {
    const snapshot: SnapshotPayload = {
      generatedAt: "2026-06-14T00:00:00+00:00",
      counts: { creators: 1, videos: 2, samples: 2 },
      samples: [
        {
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
            humanNote: "",
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
              confidence: "ok",
              basis: "relative-to-creator-baseline"
            },
            title: {
              char_len: 15,
              features: [{ id: "question", label: "疑问句式", present: true }]
            },
            cover: {
              has_asset: true,
              width: 1280,
              height: 720,
              aspect_ratio: 1.778,
              orientation: "landscape",
              cover_changed: false,
              title_changed: false
            },
            explanation: {
              structure: "标题是疑问结构。",
              features: "特征集中在真实使用疑问。",
              interpretation: "库内表现接近基线。"
            },
            caveats: ["本判断基于库内相对表现，不代表真实点击率。"]
          }
        },
        {
          id: 2,
          platform: "bilibili",
          creator: { name: "懒狗小黑", tags: [] },
          videoId: "BV2",
          title: "普通样本",
          url: "https://www.bilibili.com/video/BV2",
          publishedAt: null,
          firstSeenAt: "2026-06-14T00:00:00+00:00",
          lastSeenAt: "2026-06-14T00:00:00+00:00",
          metrics: {
            playCount: null,
            likeCount: null,
            coinCount: null,
            favoriteCount: null,
            danmakuCount: null,
            followerCount: null
          },
          cover: { url: null },
          card: {
            track: "",
            humanNote: "",
            status: "",
            baselinePlayCount: null,
            relativeToBaseline: null,
            viewsPerFollower: null
          },
          analysis: null
        }
      ]
    };
    const fetcher = vi.fn().mockResolvedValueOnce(jsonResponse(snapshot));

    const result = await loadSnapshot(fetcher);

    expect(result.payload.samples[0].analysis?.performance.bucket).toBe("steady");
    expect(result.payload.samples[1].analysis).toBeNull();
  });
});
