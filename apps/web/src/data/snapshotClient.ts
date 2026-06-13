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
}

export async function loadSnapshot(fetcher: SnapshotFetcher = fetch, options: LoadSnapshotOptions = {}): Promise<SnapshotResult> {
  try {
    const payload = await fetchSnapshot(fetcher, options.forceExport ? `${API_SNAPSHOT_PATH}?export=1` : API_SNAPSHOT_PATH);
    return { payload, source: "api" };
  } catch {
    const payload = await fetchSnapshot(fetcher, withBasePath(STATIC_SNAPSHOT_PATH));
    return { payload, source: "static" };
  }
}

export function withBasePath(path: string): string {
  if (/^(https?:)?\/\//.test(path) || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const base = import.meta.env.BASE_URL || "/";
  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  const normalizedPath = path.replace(/^\/+/, "");
  return `${normalizedBase}${normalizedPath}`;
}

async function fetchSnapshot(fetcher: SnapshotFetcher, path: string): Promise<SnapshotPayload> {
  const response = await fetcher(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`快照读取失败：${response.status}`);
  }
  return response.json() as Promise<SnapshotPayload>;
}
