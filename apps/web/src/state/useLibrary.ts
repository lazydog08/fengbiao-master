import { useMemo, useState } from "react";
import { allPerformanceBuckets, getPerformanceBucket } from "../lib/buckets";
import { filterAndSortSamples } from "../lib/search";
import { buildVideoTypeFacets } from "../lib/videoTypes";
import type { FacetOption, LibraryFilters, Sample, SortKey } from "../types";

const EMPTY_FILTERS: LibraryFilters = {
  platforms: [],
  creators: [],
  tags: [],
  buckets: [],
};

export function useLibrary(samples: Sample[]) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<LibraryFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState<SortKey>("recent");
  // Primary left-nav selection. `null` = all video types.
  const [videoType, setVideoType] = useState<string | null>(null);

  const visibleSamples = useMemo(
    () => filterAndSortSamples(samples, { query, filters, sort, videoType }),
    [samples, query, filters, sort, videoType],
  );

  const videoTypeFacets = useMemo(() => buildVideoTypeFacets(samples), [samples]);

  const facets = useMemo(
    () => ({
      platforms: buildFacet(samples, (sample) => sample.platform),
      creators: buildFacet(samples, (sample) => sample.creator.name),
      tags: buildFacet(samples, (sample) => sample.creator.tags),
      buckets: allPerformanceBuckets().map((bucket) => ({
        value: bucket.id,
        label: bucket.shortLabel,
        count: samples.filter((sample) => getPerformanceBucket(sample.card.relativeToBaseline).id === bucket.id).length,
      })),
    }),
    [samples],
  );

  function toggleFilter(group: keyof LibraryFilters, value: string) {
    setFilters((current) => {
      const existing = current[group] as string[];
      const next = existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value];
      return { ...current, [group]: next };
    });
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
  }

  return {
    query,
    setQuery,
    filters,
    toggleFilter,
    clearFilters,
    sort,
    setSort,
    videoType,
    setVideoType,
    videoTypeFacets,
    visibleSamples,
    facets,
  };
}

function buildFacet(samples: Sample[], getter: (sample: Sample) => string | string[]): FacetOption[] {
  const counts = new Map<string, number>();
  for (const sample of samples) {
    const raw = getter(sample);
    const values = Array.isArray(raw) ? raw : [raw];
    for (const value of values) {
      if (!value) {
        continue;
      }
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-CN"));
}
