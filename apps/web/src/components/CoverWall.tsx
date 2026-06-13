import { CoverTile } from "./CoverTile";
import type { Sample } from "../types";

interface CoverWallProps {
  samples: Sample[];
  selectedId: number | null;
  favorites: Set<number>;
  onOpen: (sample: Sample) => void;
  onToggleFavorite: (id: number) => void;
}

export function CoverWall({ samples, selectedId, favorites, onOpen, onToggleFavorite }: CoverWallProps) {
  return (
    <section className="sample-grid" aria-label="封标样本列表">
      {samples.map((sample) => (
        <CoverTile
          key={sample.id}
          sample={sample}
          selected={selectedId === sample.id}
          favorite={favorites.has(sample.id)}
          onOpen={onOpen}
          onToggleFavorite={onToggleFavorite}
        />
      ))}
    </section>
  );
}
