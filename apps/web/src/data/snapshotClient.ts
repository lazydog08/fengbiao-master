import type { SnapshotPayload } from "../types";

const API_SNAPSHOT_PATH = "/api/snapshot";
const STATIC_SNAPSHOT_PATH = "/fengbiao-snapshot.json";

export type SnapshotSource = "api" | "static";
export type SnapshotFetcher = typeof fetch;

export interface SnapshotResult {
  payload: SnapshotPayload;
  source: SnapshotSource;
}

export interface LoadSnapshotOptions {
  forceExport?: boolean;
  preferApi?: boolean;
}

export async function loadSnapshot(fetcher: SnapshotFetcher = fetch, options: LoadSnapshotOptions = {}): Promise<SnapshotResult> {
  const preferApi = options.preferApi ?? isLocalBrowser();
  if (preferApi) {
    try {
      const payload = await fetchSnapshot(fetcher, options.forceExport ? `${API_SNAPSHOT_PATH}?export=1` : API_SNAPSHOT_PATH);
      return { payload, source: "api" };
    } catch {
      // Fall through to the static snapshot. This is the expected path on
      // GitHub Pages and any environment without the local sync server.
    }
  }
  const payload = await fetchSnapshot(fetcher, withBasePath(STATIC_SNAPSHOT_PATH));
  return { payload, source: "static" };
}

export function withBasePath(path: string, basePath: string = import.meta.env.BASE_URL || "/"): string {
  if (/^(https?:)?\/\//.test(path) || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const normalizedBase = basePath.endsWith("/") ? basePath : `${basePath}/`;
  const normalizedPath = path.replace(/^\/+/, "");
  return `${normalizedBase}${normalizedPath}`;
}

function isLocalBrowser(): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

async function fetchSnapshot(fetcher: SnapshotFetcher, path: string): Promise<SnapshotPayload> {
  const response = await fetcher(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`快照读取失败：${response.status}`);
  }
  return response.json() as Promise<SnapshotPayload>;
}
