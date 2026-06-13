/**
 * Shared text normalization used by both the search scorer (`search.ts`) and the
 * video-type categorizer (`videoTypes.ts`).
 *
 * It lives in its own tiny module on purpose: `search.ts` needs `getVideoType`
 * from `videoTypes.ts`, and `videoTypes.ts` needs the same normalization the
 * scorer uses. Keeping the helper here lets both depend on it without importing
 * each other (which would be a circular import).
 */
export function normalizeText(value: string): string {
  return value.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
}
