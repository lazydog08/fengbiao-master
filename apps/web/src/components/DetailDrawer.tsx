import { useEffect, useRef, type KeyboardEvent } from "react";
import { Copy, ExternalLink, Star, X } from "lucide-react";
import { PerformanceBadge, PlatformBadge, TagList } from "./Badges";
import { assetUrl } from "../lib/assets";
import { formatCount, formatDate, formatRatio } from "../lib/format";
import type { Sample } from "../types";

interface DetailDrawerProps {
  sample: Sample | null;
  favorite: boolean;
  onClose: () => void;
  onToggleFavorite: (id: number) => void;
}

export function DetailDrawer({ sample, favorite, onClose, onToggleFavorite }: DetailDrawerProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!sample) {
      return;
    }
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus({ preventScroll: true });

    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus({ preventScroll: true });
    };
  }, [sample]);

  if (!sample) {
    return null;
  }

  const coverUrl = assetUrl(sample.cover.url);

  function copyTitle() {
    if (!sample) {
      return;
    }
    void navigator.clipboard?.writeText(sample.title);
  }

  function trapFocus(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") {
      return;
    }
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'),
    );
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="drawer-layer" role="dialog" aria-modal="true" aria-label="样本详情" onMouseDown={onClose}>
      <aside className="detail-drawer" onMouseDown={(event) => event.stopPropagation()} onKeyDown={trapFocus}>
        <div className="drawer-actions">
          <button className={`icon-button ${favorite ? "active" : ""}`} type="button" onClick={() => onToggleFavorite(sample.id)} title={favorite ? "取消收藏" : "收藏样本"} aria-label={favorite ? "取消收藏" : "收藏样本"}>
            <Star size={18} fill={favorite ? "currentColor" : "none"} />
          </button>
          <button className="icon-button" type="button" onClick={copyTitle} title="复制标题" aria-label="复制标题">
            <Copy size={18} />
          </button>
          <a className="icon-button" href={sample.url} target="_blank" rel="noreferrer" title="打开原视频" aria-label="打开原视频">
            <ExternalLink size={18} />
          </a>
          <button ref={closeButtonRef} className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-cover">
          {coverUrl ? (
            <img src={coverUrl} alt={`${sample.creator.name}《${sample.title}》封面大图`} />
          ) : (
            <div className="cover-missing large">
              <span>{sample.platform}</span>
              <strong>{sample.title}</strong>
            </div>
          )}
        </div>

        <div className="drawer-body">
          <div className="drawer-badges">
            <div className="drawer-badge-field">
              <span className="drawer-badge-label">平台</span>
              <PlatformBadge platform={sample.platform} />
            </div>
            <div className="drawer-badge-field">
              <span className="drawer-badge-label">表现</span>
              <PerformanceBadge sample={sample} />
            </div>
          </div>
          <h2>{sample.title}</h2>
          <p className="creator-line">{sample.creator.name}</p>
          <TagList tags={sample.creator.tags} />

          <dl className="metric-grid">
            <div>
              <dt>播放量</dt>
              <dd>{formatCount(sample.metrics.playCount)}</dd>
            </div>
            <div>
              <dt>库内相对表现</dt>
              <dd>{formatRatio(sample.card.relativeToBaseline)}</dd>
            </div>
            <div>
              <dt>库内基线</dt>
              <dd>{formatCount(sample.card.baselinePlayCount)}</dd>
            </div>
            <div>
              <dt>播放/粉丝</dt>
              <dd>{formatRatio(sample.card.viewsPerFollower)}</dd>
            </div>
          </dl>

          <section className="drawer-section">
            <h3>可复用观察</h3>
            <p>{sample.card.humanNote || sample.creator.note || "这条样本还没有人工备注，先从封面构图、标题钩子和数据表现里找相似题材。"}</p>
          </section>

          <section className="drawer-section">
            <h3>收录信息</h3>
            <dl className="info-list">
              <div>
                <dt>发布时间</dt>
                <dd>{formatDate(sample.publishedAt)}</dd>
              </div>
              <div>
                <dt>最近收录</dt>
                <dd>{formatDate(sample.lastSeenAt)}</dd>
              </div>
              <div>
                <dt>赛道</dt>
                <dd>{sample.card.track || "—"}</dd>
              </div>
            </dl>
            <p className="fine-print">B站样本来自公开搜索结果，通常每账号约 3 条近期视频；库内相对表现基于该创作者当前样本的中位数。</p>
          </section>
        </div>
      </aside>
    </div>
  );
}
