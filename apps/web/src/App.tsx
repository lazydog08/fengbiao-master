import { useEffect, useMemo, useState } from "react";
import { CoverWall } from "./components/CoverWall";
import { DetailDrawer } from "./components/DetailDrawer";
import { EmptyState } from "./components/EmptyState";
import { Toolbar } from "./components/Toolbar";
import { VideoTypeNav } from "./components/VideoTypeNav";
import { useSnapshot } from "./data/useSnapshot";
import { useFavorites } from "./state/useFavorites";
import { useLibrary } from "./state/useLibrary";
import type { Sample } from "./types";

export default function App() {
  const { data, loading, refreshing, error, refresh } = useSnapshot();
  const samples = data?.samples ?? [];
  const library = useLibrary(samples);
  const { favorites, isFavorite, toggleFavorite } = useFavorites();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selectedSample = useMemo(
    () => samples.find((sample) => sample.id === selectedId) ?? null,
    [samples, selectedId],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSelectedId(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  function openSample(sample: Sample) {
    setSelectedId(sample.id);
  }

  if (loading) {
    return <EmptyState title="正在读取封标快照" body="如果这里停太久，先跑导出脚本生成前端快照。" />;
  }

  if (error) {
    return <EmptyState title="快照读取失败" body={error} />;
  }

  if (!data || samples.length === 0) {
    return <EmptyState title="暂无样本" body="导出快照后，这里会直接进入真实样本库。" />;
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <strong>封标大师</strong>
          <span>懒狗小黑的封面 / 标题样本库</span>
        </div>
        <VideoTypeNav
          facets={library.videoTypeFacets}
          total={samples.length}
          value={library.videoType}
          onSelect={library.setVideoType}
        />
      </aside>

      <main className="app-main">
        <Toolbar
          query={library.query}
          onQueryChange={library.setQuery}
          filters={library.filters}
          onToggleFilter={library.toggleFilter}
          onClearFilters={library.clearFilters}
          sort={library.sort}
          onSortChange={library.setSort}
          facets={library.facets}
          activeType={library.videoType}
          total={samples.length}
          visible={library.visibleSamples.length}
          generatedAt={data.generatedAt}
          refreshing={refreshing}
          onRefresh={refresh}
        />
        {library.visibleSamples.length > 0 ? (
          <CoverWall
            samples={library.visibleSamples}
            selectedId={selectedId}
            favorites={favorites}
            onOpen={openSample}
            onToggleFavorite={toggleFavorite}
          />
        ) : (
          <EmptyState title="没有命中的样本" body="换一个选题词、切换左侧类型，或减少筛选条件。" />
        )}
      </main>

      <DetailDrawer
        sample={selectedSample}
        favorite={selectedSample ? isFavorite(selectedSample.id) : false}
        onClose={() => setSelectedId(null)}
        onToggleFavorite={toggleFavorite}
      />
    </div>
  );
}
