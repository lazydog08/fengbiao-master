import { Filter, RefreshCw, Search, SlidersHorizontal, X } from "lucide-react";
import { allPerformanceBuckets } from "../lib/buckets";
import type { FacetOption, LibraryFilters, SortKey } from "../types";

interface ToolbarProps {
  query: string;
  onQueryChange: (value: string) => void;
  filters: LibraryFilters;
  onToggleFilter: (group: keyof LibraryFilters, value: string) => void;
  onClearFilters: () => void;
  sort: SortKey;
  onSortChange: (sort: SortKey) => void;
  facets: {
    platforms: FacetOption[];
    creators: FacetOption[];
    tags: FacetOption[];
    buckets: FacetOption[];
  };
  activeType: string | null;
  total: number;
  visible: number;
  generatedAt: string;
  refreshing: boolean;
  onRefresh: () => void;
}

export function Toolbar({
  query,
  onQueryChange,
  filters,
  onToggleFilter,
  onClearFilters,
  sort,
  onSortChange,
  facets,
  activeType,
  total,
  visible,
  generatedAt,
  refreshing,
  onRefresh,
}: ToolbarProps) {
  const hasFilters = Object.values(filters).some((values) => values.length > 0);

  return (
    <header className="toolbar">
      <div className="view-block">
        <h1 className="view-title">{activeType ?? "全部样本"}</h1>
        <span className="view-sub">
          {visible}/{total} 个样本 · 快照 {formatSnapshotTime(generatedAt)}
        </span>
      </div>

      <label className="search-box">
        <Search size={18} />
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="智能眼镜、3D 打印、别墅 DIY、iPhone 选题"
          aria-label="搜索封标样本"
        />
        {query ? (
          <button className="icon-button" type="button" onClick={() => onQueryChange("")} title="清空搜索" aria-label="清空搜索">
            <X size={16} />
          </button>
        ) : null}
      </label>

      <div className="toolbar-controls">
        <button
          className="icon-button sync-refresh"
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          title={refreshing ? "正在刷新快照" : "刷新快照"}
          aria-label="刷新快照"
        >
          <RefreshCw size={16} className={refreshing ? "spin" : undefined} />
        </button>

        <label className="select-control" title="排序">
          <SlidersHorizontal size={16} />
          <select value={sort} onChange={(event) => onSortChange(event.target.value as SortKey)} aria-label="排序">
            <option value="recent">最近收录</option>
            <option value="play">播放量</option>
            <option value="relative">库内相对表现</option>
          </select>
        </label>

        <details className="filter-menu">
          <summary title="筛选">
            <Filter size={16} />
            筛选
          </summary>
          <div className="filter-panel">
            <FilterGroup title="平台" group="platforms" options={facets.platforms} selected={filters.platforms} onToggle={onToggleFilter} />
            <FilterGroup title="创作者" group="creators" options={facets.creators} selected={filters.creators} onToggle={onToggleFilter} limit={12} />
            <FilterGroup title="标签" group="tags" options={facets.tags} selected={filters.tags} onToggle={onToggleFilter} limit={16} />
            <FilterGroup
              title="表现"
              group="buckets"
              options={allPerformanceBuckets().map((bucket) => ({
                value: bucket.id,
                label: bucket.shortLabel,
                count: facets.buckets.find((item) => item.value === bucket.id)?.count ?? 0,
              }))}
              selected={filters.buckets}
              onToggle={onToggleFilter}
            />
            {hasFilters ? (
              <button className="clear-filter" type="button" onClick={onClearFilters}>
                清空筛选
              </button>
            ) : null}
          </div>
        </details>
      </div>
    </header>
  );
}

function FilterGroup({
  title,
  group,
  options,
  selected,
  onToggle,
  limit,
}: {
  title: string;
  group: keyof LibraryFilters;
  options: FacetOption[];
  selected: string[];
  onToggle: (group: keyof LibraryFilters, value: string) => void;
  limit?: number;
}) {
  return (
    <fieldset className="filter-group">
      <legend>{title}</legend>
      <div className="filter-options">
        {options.slice(0, limit ?? options.length).map((option) => (
          <label key={option.value}>
            <input type="checkbox" checked={selected.includes(option.value)} onChange={() => onToggle(group, option.value)} />
            <span>{option.label}</span>
            <em>{option.count}</em>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function formatSnapshotTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}
