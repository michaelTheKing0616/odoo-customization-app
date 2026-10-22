"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type LiveSnapshot, type SnapshotModelDetail } from "@/lib/api";

type Load<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T };

function message(err: unknown): string {
  const text = err instanceof Error ? err.message : String(err ?? "");
  return text || "Couldn't reach your database.";
}

/** Overview live picture. Read-only; reuses the API's per-connection snapshot cache. */
export function useLiveSnapshot(connectionId: string) {
  const [state, setState] = useState<Load<LiveSnapshot>>({ status: "loading" });
  const load = useCallback((opts: { refresh?: boolean } = {}) => {
    if (!opts.refresh) setState({ status: "loading" });
    api
      .getLiveSnapshot(connectionId, opts.refresh ? { refresh: true } : {})
      .then((data) => setState({ status: "ready", data }))
      .catch((err) => setState({ status: "error", message: message(err) }));
  }, [connectionId]);
  useEffect(() => load(), [load]);
  return { state, reload: () => load(), refresh: () => load({ refresh: true }) };
}

/** Lazy per-model detail, cached in memory for this page visit. */
export function useModelDetail(connectionId: string) {
  const [selected, setSelected] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, Load<SnapshotModelDetail>>>({});
  // Read the cache through a ref so ``open`` stays stable (safe as an effect dependency).
  const cacheRef = useRef(cache);
  cacheRef.current = cache;
  const open = useCallback(
    (model: string) => {
      setSelected(model);
      const hit = cacheRef.current[model]?.status;
      if (hit === "ready" || hit === "loading") return;
      setCache((c) => ({ ...c, [model]: { status: "loading" } }));
      api
        .getSnapshotModel(connectionId, model)
        .then((data) => setCache((c) => ({ ...c, [model]: { status: "ready", data } })))
        .catch((err) => setCache((c) => ({ ...c, [model]: { status: "error", message: message(err) } })));
    },
    [connectionId],
  );
  const close = useCallback(() => setSelected(null), []);
  /** Re-read one model after an Apply (server cache dropped), keeping the current view on screen. */
  const refresh = useCallback(
    (model: string) => {
      api
        .getSnapshotModel(connectionId, model, { refresh: true })
        .then((data) => setCache((c) => ({ ...c, [model]: { status: "ready", data } })))
        .catch((err) => setCache((c) => ({ ...c, [model]: { status: "error", message: message(err) } })));
    },
    [connectionId],
  );
  return { selected, detail: selected ? cache[selected] : undefined, open, close, refresh };
}
