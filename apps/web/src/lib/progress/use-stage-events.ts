"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { StageEvent } from "@/lib/api/progress";

const POLL_MS = 800;

export function useStageEvents(runId: string | null | undefined, enabled: boolean) {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const afterRef = useRef(0);

  useEffect(() => {
    if (!enabled || !runId) {
      setEvents([]);
      afterRef.current = 0;
      return;
    }
    let cancelled = false;
    afterRef.current = 0;

    const tick = async () => {
      try {
        const res = await api.stageEvents(runId, afterRef.current);
        if (cancelled) return;
        if (res.events.length) {
          setEvents((prev) => [...prev, ...res.events]);
          afterRef.current = res.total;
        }
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Progress unavailable");
        }
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [enabled, runId]);

  const latest = events.length ? events[events.length - 1] : null;
  return { events, latest, error };
}
