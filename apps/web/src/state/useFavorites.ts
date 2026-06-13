import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "fengbiao-master-favorites";

export function useFavorites() {
  const [favorites, setFavorites] = useState<Set<number>>(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? (JSON.parse(raw) as number[]) : [];
      return new Set(Array.isArray(parsed) ? parsed : []);
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]));
    } catch {
      // Favorite marks are a convenience layer; browsing should keep working if storage is blocked.
    }
  }, [favorites]);

  const toggleFavorite = useCallback((id: number) => {
    setFavorites((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  return {
    favorites,
    toggleFavorite,
    isFavorite: useCallback((id: number) => favorites.has(id), [favorites]),
  };
}
