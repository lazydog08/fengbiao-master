import { useCallback, useEffect, useState } from "react";
import { loadSnapshot, type SnapshotSource } from "./snapshotClient";
import type { SnapshotPayload } from "../types";

interface SnapshotState {
  data: SnapshotPayload | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  source: SnapshotSource | null;
  refresh: () => void;
}

export function useSnapshot(): SnapshotState {
  const [request, setRequest] = useState({ id: 0, forceExport: false });
  const [state, setState] = useState<Omit<SnapshotState, "refresh">>({
    data: null,
    loading: true,
    refreshing: false,
    error: null,
    source: null,
  });

  useEffect(() => {
    let alive = true;
    setState((current) => ({ ...current, loading: current.data === null, refreshing: current.data !== null, error: null }));

    loadSnapshot(fetch, { forceExport: request.forceExport })
      .then(({ payload, source }) => {
        if (alive) {
          setState({ data: payload, loading: false, refreshing: false, error: null, source });
        }
      })
      .catch((error: unknown) => {
        if (alive) {
          setState({
            data: null,
            loading: false,
            refreshing: false,
            error: error instanceof Error ? error.message : "快照读取失败",
            source: null,
          });
        }
      });

    return () => {
      alive = false;
    };
  }, [request]);

  const refresh = useCallback(() => setRequest((current) => ({ id: current.id + 1, forceExport: true })), []);

  return { ...state, refresh };
}
