import type { VideoTypeFacet } from "../lib/videoTypes";

interface VideoTypeNavProps {
  facets: VideoTypeFacet[];
  total: number;
  value: string | null;
  onSelect: (value: string | null) => void;
}

/**
 * Primary navigation: video types only (no creator/platform categories).
 *
 * One DOM for both layouts — CSS turns the vertical desktop rail into a
 * horizontal, scrollable tab strip on narrow screens. Empty types stay visible
 * (so the taxonomy is predictable as the library grows) but are disabled.
 */
export function VideoTypeNav({ facets, total, value, onSelect }: VideoTypeNavProps) {
  return (
    <nav className="type-nav" aria-label="视频类型导航">
      <p className="type-nav-title">视频类型</p>
      <div className="type-nav-list" role="list">
        <button
          type="button"
          role="listitem"
          className={`type-chip ${value === null ? "active" : ""}`}
          aria-pressed={value === null}
          onClick={() => onSelect(null)}
        >
          <span className="type-chip-label">全部</span>
          <span className="type-chip-count">{total}</span>
        </button>

        {facets.map((facet) => {
          const empty = facet.count === 0;
          const active = value === facet.value;
          return (
            <button
              key={facet.value}
              type="button"
              role="listitem"
              className={`type-chip ${active ? "active" : ""} ${empty ? "empty" : ""}`}
              aria-pressed={active}
              disabled={empty}
              onClick={() => onSelect(facet.value)}
            >
              <span className="type-chip-label">{facet.label}</span>
              <span className="type-chip-count">{facet.count}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
