"use client";

import { useCallback, useRef, useState } from "react";
import {
  DESIGNER_HISTORY_CAP,
  DESIGNER_HISTORY_COALESCE_MS,
  designerHistoryIsDirty,
  markDesignerHistoryPublished,
  pushDesignerHistory,
  redoDesignerHistory,
  resetDesignerHistory,
  undoDesignerHistory,
  type DesignerHistoryPushMeta,
  type DesignerHistoryState,
} from "@/lib/designerHistory";

type RecordMeta = Pick<DesignerHistoryPushMeta, "label" | "coalesceKey">;

export function useDesignerHistory<T>(options?: {
  cap?: number;
  coalesceMs?: number;
}) {
  const cap = options?.cap ?? DESIGNER_HISTORY_CAP;
  const coalesceMs = options?.coalesceMs ?? DESIGNER_HISTORY_COALESCE_MS;
  const stateRef = useRef<DesignerHistoryState<T> | null>(null);
  const [, setTick] = useState(0);
  const bump = useCallback(() => setTick((n) => n + 1), []);

  const reset = useCallback(
    (present: T) => {
      stateRef.current = resetDesignerHistory(present);
      bump();
    },
    [bump],
  );

  const record = useCallback(
    (next: T, meta?: RecordMeta) => {
      const current = stateRef.current;
      if (!current) {
        stateRef.current = resetDesignerHistory(next);
        bump();
        return;
      }
      const pushed = pushDesignerHistory(current, next, { ...meta, cap, coalesceMs });
      if (pushed === current) return;
      stateRef.current = pushed;
      bump();
    },
    [bump, cap, coalesceMs],
  );

  const undo = useCallback((): T | null => {
    const current = stateRef.current;
    if (!current) return null;
    const result = undoDesignerHistory(current);
    if (!result) return null;
    stateRef.current = result.state;
    bump();
    return result.snapshot;
  }, [bump]);

  const redo = useCallback((): T | null => {
    const current = stateRef.current;
    if (!current) return null;
    const result = redoDesignerHistory(current);
    if (!result) return null;
    stateRef.current = result.state;
    bump();
    return result.snapshot;
  }, [bump]);

  const markPublished = useCallback(() => {
    const current = stateRef.current;
    if (!current) return;
    stateRef.current = markDesignerHistoryPublished(current);
    bump();
  }, [bump]);

  const state = stateRef.current;
  return {
    canUndo: (state?.past.length ?? 0) > 0,
    canRedo: (state?.future.length ?? 0) > 0,
    dirty: state ? designerHistoryIsDirty(state) : false,
    undoLabel: state?.past[state.past.length - 1]?.label,
    redoLabel: state?.future[0]?.label,
    record,
    undo,
    redo,
    reset,
    markPublished,
  };
}
