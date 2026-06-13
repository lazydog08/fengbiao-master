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
    expect(withBasePath("https://example.com/cover.jpg")).toBe("https://example.com/cover.jpg");
  });
});
