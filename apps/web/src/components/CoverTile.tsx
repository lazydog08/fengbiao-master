import { Star } from "lucide-react";
import { PerformanceBadge, PlatformBadge } from "./Badges";
import { assetUrl } from "../lib/assets";
import { formatCount } from "../lib/format";
import type { Sample } from "../types";

interface CoverTileProps {
  sample: Sample;
  selected: boolean;
  favorite: boolean;
  onOpen: (sample: Sample) => void;
  onToggleFavorite: (id: number) => void;
}

/**
 * A calm archive card: the cover image and the text live in separate areas, so
 * nothing is printed on top of the thumbnail. The title is always visible (title
 * is half of 封标), and platform / performance / play count sit in the meta block
 * below the image.
 */
export function CoverTile({ sample, selected, favorite, onOpen, onToggleFavorite }: CoverTileProps) {
  const plays = formatCount(sample.metrics.playCount);
  const coverUrl = assetUrl(sample.cover.url);

  return (
    <article className={`sample-card ${selected ? "selected" : ""}`}>
      <button
        className="sample-cover"
        type="button"
        onClick={() => onOpen(sample)}
        aria-label={`打开样本：${sample.title}`}
      >
        {coverUrl ? (
          <img
            loading="lazy"
            decoding="async"
            src={coverUrl}
            alt={`${sample.creator.name}《${sample.title}》封面`}
          />
        ) : (
          <div className="cover-missing">
            <span>{platformText(sample.platform)}</span>
            <span className="cover-missing-hint">暂无封面</span>
          </div>
        )}
      </button>

      <div className="sample-body">
        <button className="sample-title" type="button" onClick={() => onOpen(sample)} title={sample.title}>
          {sample.title}
        </button>

        <div className="sample-meta">
          <PlatformBadge platform={sample.platform} />
          <span className="sample-creator" title={sample.creator.name}>
            {sample.creator.name}
          </span>
        </div>

        <div className="sample-stats">
          <span className="sample-plays">
            {plays === "—" ? "播放量未公开" : `${plays} 播放`}
          </span>
          <PerformanceBadge sample={sample} />
          <button
            className={`icon-button favorite-toggle ${favorite ? "active" : ""}`}
            type="button"
            onClick={() => onToggleFavorite(sample.id)}
            title={favorite ? "取消收藏" : "收藏样本"}
            aria-label={favorite ? "取消收藏" : "收藏样本"}
            aria-pressed={favorite}
          >
            <Star size={16} fill={favorite ? "currentColor" : "none"} />
          </button>
        </div>
      </div>
    </article>
  );
}

function platformText(platform: string): string {
  if (platform === "bilibili") {
    return "B站";
  }
  if (platform === "youtube") {
    return "YouTube";
  }
  return platform;
}
