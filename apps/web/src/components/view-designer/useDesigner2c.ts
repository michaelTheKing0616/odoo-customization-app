"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { EngineOp, EngineRecord, EngineViewType } from "@/lib/api/view-engine";
import type { Heat, TourStep } from "@/lib/api/view-engine-2c";

type DesignerLike = {
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  ops: EngineOp[];
  addOps: (ops: EngineOp[], summary: string) => void;
  selectedId: string | null;
  tree: unknown;
  lastPublish: { version_id?: string | null } | null;
};

export const COEDIT_MS = 1500;

function newEditorId(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  return c?.randomUUID ? c.randomUUID() : `ed-${Math.random().toString(36).slice(2, 12)}`;
}

/**
 * Stage 2c state around the designer: overlays (heatmap, sample record, vision
 * simulation, guided tour), live co-editing and the post-publish watch.
 */
export function useDesigner2c(s: DesignerLike, connectionId: string) {
  const [heat, setHeat] = useState<Record<string, Heat> | null>(null);
  const [sample, setSample] = useState<EngineRecord | null>(null);
  const [simulate, setSimulate] = useState("");
  const [tour, setTour] = useState<TourStep[] | null>(null);
  const [tourAt, setTourAt] = useState(0);
  const [others, setOthers] = useState<Array<{ editor_id: string; name: string; selected: string | null }>>([]);
  const editorId = useRef(newEditorId());
  const seq = useRef(0);
  const synced = useRef(0); // how many of s.ops the room already has
  const opsRef = useRef(s.ops);
  opsRef.current = s.ops;
  const selRef = useRef(s.selectedId);
  selRef.current = s.selectedId;
  const addOpsRef = useRef(s.addOps);
  addOpsRef.current = s.addOps;

  // New screen: overlays and the shared room start over.
  useEffect(() => {
    setHeat(null);
    setSample(null);
    setTour(null);
    setOthers([]);
    seq.current = 0;
    synced.current = 0;
  }, [connectionId, s.model, s.viewType, s.viewId]);

  // Live co-editing: share selections and draft changes every 1.5 s.
  useEffect(() => {
    if (!s.tree) return;
    let live = true;
    let ctrl: AbortController | null = null;
    const tick = async () => {
      const ops = opsRef.current;
      if (ops.length < synced.current) synced.current = ops.length; // undo: not shared
      const mine = ops.slice(synced.current);
      ctrl = new AbortController();
      try {
        const out = await api.coedit(
          connectionId,
          { model: s.model, view_type: s.viewType, view_id: s.viewId, editor_id: editorId.current, name: "Someone", selected: selRef.current,
            since: seq.current, base_seq: seq.current, ops: mine },
          ctrl.signal,
        );
        if (!live) return;
        synced.current += mine.length - out.refused.length;
        if (out.refused.length) {
          toast(out.refused[0].reason, { description: "Your change to that item wasn't shared. Their version stays." });
        }
        seq.current = out.seq;
        setOthers(out.others);
        if (out.ops.length) {
          const incoming = out.ops.map((o) => o.op);
          const who = Array.from(new Set(out.ops.map((o) => o.name))).join(", ");
          addOpsRef.current(incoming, `${who} changed ${incoming.length} item${incoming.length === 1 ? "" : "s"}`);
          synced.current += incoming.length;
        }
      } catch {
        // offline or the server restarted: try again on the next tick
      }
    };
    const id = window.setInterval(() => void tick(), COEDIT_MS);
    return () => {
      live = false;
      ctrl?.abort();
      window.clearInterval(id);
    };
  }, [connectionId, s.model, s.viewType, s.viewId, s.tree]);

  // After every publish: watch it (5 min, 1 h, 1 day) with a one-click undo.
  const watched = useRef<string | null>(null);
  useEffect(() => {
    const vid = s.lastPublish?.version_id;
    if (!vid || watched.current === vid) return;
    watched.current = vid;
    api.watchStart(connectionId, { model: s.model, view_type: s.viewType, view_id: s.viewId, version_id: vid }).catch(() => undefined);
  }, [s.lastPublish, connectionId, s.model, s.viewType, s.viewId]);

  const cursors = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const o of others) if (o.selected) (out[o.selected] ??= []).push(o.name);
    return out;
  }, [others]);

  return {
    heat,
    setHeat,
    sample,
    setSample,
    simulate,
    setSimulate,
    tour,
    tourAt,
    setTourAt,
    startTour: (steps: TourStep[]) => {
      setTour(steps.length ? steps : null);
      setTourAt(0);
    },
    endTour: () => setTour(null),
    tourFocus: tour ? tour[Math.min(tourAt, tour.length - 1)]?.node ?? null : null,
    others,
    cursors,
  };
}
