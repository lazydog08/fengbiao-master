import { useEffect, useRef, type KeyboardEvent } from "react";
import { Copy, ExternalLink, Star, X } from "lucide-react";
import { PerformanceBadge, PlatformBadge, TagList } from "./Badges";
import { assetUrl } from "../lib/assets";
import { getPerformanceBucket } from "../lib/buckets";
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
  const analysis = completeV1Analysis(sample.analysis);
  const bucket = getPerformanceBucket(sample.card.relativeToBaseline);
  const analysisFeatures = analysis?.title.features.filter((feature) => feature.present) ?? [];
  const needsCaution = analysis?.performance.confidence === "low" || bucket.id === "unknown";
  const originalVideoUrl = safeExternalUrl(sample.url);
  const coverAlt = `${sample.creator.name}《${sample.title}》封面大图`;

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
          {originalVideoUrl ? (
            <a className="icon-button" href={originalVideoUrl} target="_blank" rel="noreferrer" title="快捷打开原视频" aria-label="快捷打开原视频，新标签页打开">
              <ExternalLink size={18} aria-hidden="true" />
            </a>
          ) : null}
          <button ref={closeButtonRef} className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-cover">
          {coverUrl ? (
            originalVideoUrl ? (
              <a className="drawer-cover-link" href={originalVideoUrl} target="_blank" rel="noreferrer" aria-label={`打开《${sample.title}》原视频，新标签页打开`}>
                <img src={coverUrl} alt={coverAlt} />
                <span className="drawer-cover-link-badge" aria-hidden="true">
                  <ExternalLink size={15} aria-hidden="true" />
                  <span>点击封面打开原视频</span>
                </span>
              </a>
            ) : (
              <img src={coverUrl} alt={coverAlt} />
            )
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

          {analysis ? (
            <>
              <section className="drawer-section">
                <h3>封标结构</h3>
                <p>{analysis.explanation.structure}</p>
              </section>

              <section className="drawer-section">
                <h3>特征</h3>
                {analysisFeatures.length > 0 ? (
                  <div className="analysis-feature-list">
                    {analysisFeatures.map((feature) => (
                      <span className="analysis-chip" key={feature.id}>
                        {feature.label}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="muted-note">暂未识别出明确的标题结构特征。</p>
                )}
                <p>{analysis.explanation.features}</p>
                <p className="analysis-meta">{coverSummary(analysis.cover)}</p>
              </section>

              <section className="drawer-section">
                <h3>表现判断</h3>
                <p>
                  {bucket.label}，当前库内相对表现为 {formatRatio(sample.card.relativeToBaseline)}。
                  {needsCaution ? " 数据不足，仅供参考。" : ""}
                </p>
              </section>

              <section className="drawer-section">
                <h3>为什么可能高 / 一般 / 较差</h3>
                <p>{analysis.explanation.interpretation}</p>
                {analysis.caveats.length > 0 ? (
                  <ul className="caveat-list">
                    {analysis.caveats.map((caveat) => (
                      <li key={caveat}>{caveat}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            </>
          ) : null}

          <section className="drawer-section">
            <h3>人工备注</h3>
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

function coverSummary(cover: NonNullable<Sample["analysis"]>["cover"]): string {
  if (!cover.has_asset) {
    return "封面文件暂不可读，当前分析以标题为主。";
  }
  const size = cover.width && cover.height ? `${cover.width}x${cover.height}` : "尺寸未知";
  const ratio = cover.aspect_ratio == null ? "比例未知" : `比例 ${cover.aspect_ratio}`;
  const changes = [
    cover.cover_changed ? "封面有变更记录" : null,
    cover.title_changed ? "标题有变更记录" : null,
  ].filter(Boolean);
  const changeText = changes.length > 0 ? `，${changes.join("，")}` : "";
  return `封面：${orientationLabel(cover.orientation)}，${size}，${ratio}${changeText}。`;
}

function orientationLabel(orientation: string): string {
  if (orientation === "landscape") {
    return "横版";
  }
  if (orientation === "portrait") {
    return "竖版";
  }
  if (orientation === "square") {
    return "近方形";
  }
  return "未知方向";
}

function safeExternalUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const url = new URL(trimmed);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function completeV1Analysis(analysis: Sample["analysis"]): NonNullable<Sample["analysis"]> | null {
  if (!isRecord(analysis) || analysis.version !== 1) {
    return null;
  }
  if (!isRecord(analysis.performance) || typeof analysis.performance.confidence !== "string") {
    return null;
  }
  if (!isRecord(analysis.title) || !Array.isArray(analysis.title.features)) {
    return null;
  }
  if (!analysis.title.features.every(isAnalysisFeature)) {
    return null;
  }
  if (!isRecord(analysis.cover) || typeof analysis.cover.has_asset !== "boolean") {
    return null;
  }
  if (!isRecord(analysis.explanation)) {
    return null;
  }
  if (
    typeof analysis.explanation.structure !== "string" ||
    typeof analysis.explanation.features !== "string" ||
    typeof analysis.explanation.interpretation !== "string"
  ) {
    return null;
  }
  if (!Array.isArray(analysis.caveats) || !analysis.caveats.every((caveat) => typeof caveat === "string")) {
    return null;
  }
  return analysis;
}

function isAnalysisFeature(feature: unknown): feature is NonNullable<Sample["analysis"]>["title"]["features"][number] {
  return (
    isRecord(feature) &&
    typeof feature.id === "string" &&
    typeof feature.label === "string" &&
    typeof feature.present === "boolean"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
