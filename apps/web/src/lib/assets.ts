import { withBasePath } from "../data/snapshotClient";

export function assetUrl(path: string | null | undefined): string | null {
  if (!path) {
    return null;
  }
  return withBasePath(path);
}
