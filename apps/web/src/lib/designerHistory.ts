/** Pure in-session undo/redo stack for View Designer canvas state. */

export const DESIGNER_HISTORY_CAP = 50;
export const DESIGNER_HISTORY_COALESCE_MS = 500;

export type DesignerHistoryEntry<T> = {
  snapshot: T;
  label: string;
  coalesceKey?: string;
  at: number;
};

export type DesignerHistoryState<T> = {
  past: DesignerHistoryEntry<T>[];
  present: T;
  future: DesignerHistoryEntry<T>[];
  baseline: T;
  lastCoalesceKey?: string;
  lastPushAt: number;
};

export type DesignerHistoryPushMeta = {
  label?: string;
  coalesceKey?: string;
  now?: number;
  cap?: number;
  coalesceMs?: number;
};

export function cloneDesignerSnapshot<T>(snapshot: T): T {
  return JSON.parse(JSON.stringify(snapshot)) as T;
}

export function designerSnapshotsEqual<T>(left: T, right: T): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function resetDesignerHistory<T>(present: T): DesignerHistoryState<T> {
  const snapshot = cloneDesignerSnapshot(present);
  return {
    past: [],
    present: snapshot,
    future: [],
    baseline: cloneDesignerSnapshot(present),
    lastCoalesceKey: undefined,
    lastPushAt: 0,
  };
}

export function designerHistoryIsDirty<T>(state: DesignerHistoryState<T>): boolean {
  return !designerSnapshotsEqual(state.present, state.baseline);
}

export function pushDesignerHistory<T>(
  state: DesignerHistoryState<T>,
  next: T,
  meta: DesignerHistoryPushMeta = {},
): DesignerHistoryState<T> {
  if (designerSnapshotsEqual(state.present, next)) {
    return state;
  }
  const now = meta.now ?? Date.now();
  const cap = meta.cap ?? DESIGNER_HISTORY_CAP;
  const coalesceMs = meta.coalesceMs ?? DESIGNER_HISTORY_COALESCE_MS;
  const label = meta.label ?? "Edit canvas";
  const coalesceKey = meta.coalesceKey;
  const canCoalesce =
    Boolean(coalesceKey) &&
    coalesceKey === state.lastCoalesceKey &&
    now - state.lastPushAt < coalesceMs &&
    state.past.length > 0;

  if (canCoalesce) {
    return {
      ...state,
      present: cloneDesignerSnapshot(next),
      future: [],
      lastPushAt: now,
      lastCoalesceKey: coalesceKey,
    };
  }

  const past = [
    ...state.past,
    {
      snapshot: cloneDesignerSnapshot(state.present),
      label,
      coalesceKey,
      at: now,
    },
  ];
  while (past.length > cap) {
    past.shift();
  }
  return {
    past,
    present: cloneDesignerSnapshot(next),
    future: [],
    baseline: state.baseline,
    lastCoalesceKey: coalesceKey,
    lastPushAt: now,
  };
}

export function undoDesignerHistory<T>(
  state: DesignerHistoryState<T>,
): { state: DesignerHistoryState<T>; snapshot: T } | null {
  const previous = state.past[state.past.length - 1];
  if (!previous) return null;
  const past = state.past.slice(0, -1);
  const future: DesignerHistoryEntry<T>[] = [
    {
      snapshot: cloneDesignerSnapshot(state.present),
      label: previous.label,
      at: previous.at,
    },
    ...state.future,
  ];
  const present = cloneDesignerSnapshot(previous.snapshot);
  return {
    snapshot: present,
    state: {
      past,
      present,
      future,
      baseline: state.baseline,
      lastCoalesceKey: undefined,
      lastPushAt: 0,
    },
  };
}

export function redoDesignerHistory<T>(
  state: DesignerHistoryState<T>,
): { state: DesignerHistoryState<T>; snapshot: T } | null {
  const next = state.future[0];
  if (!next) return null;
  const future = state.future.slice(1);
  const past: DesignerHistoryEntry<T>[] = [
    ...state.past,
    {
      snapshot: cloneDesignerSnapshot(state.present),
      label: next.label,
      at: next.at,
    },
  ];
  const present = cloneDesignerSnapshot(next.snapshot);
  return {
    snapshot: present,
    state: {
      past,
      present,
      future,
      baseline: state.baseline,
      lastCoalesceKey: undefined,
      lastPushAt: 0,
    },
  };
}

export function markDesignerHistoryPublished<T>(
  state: DesignerHistoryState<T>,
): DesignerHistoryState<T> {
  return resetDesignerHistory(state.present);
}
