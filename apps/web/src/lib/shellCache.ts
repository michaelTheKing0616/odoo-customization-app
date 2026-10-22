/**
 * Touch 142: instant shell. The app frame paints from the last known connection and list, then live data streams in.
 * Only non-secret fields are kept; anything that looks like a credential is dropped before saving.
 */
const KEY = "ingenium.shell-cache.v1";
const SECRET = /pass|secret|token|key|credential|cookie/i;

export function scrub<T>(v: T): T {
  if (Array.isArray(v)) return v.map(scrub) as T;
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.entries(v as Record<string, unknown>).filter(([k]) => !SECRET.test(k)).map(([k, x]) => [k, scrub(x)])) as T;
  }
  return v;
}

function readAll(): Record<string, unknown> {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, unknown>; } catch { return {}; }
}

export function readShell<T>(name: string): T | undefined {
  return readAll()[name] as T | undefined;
}

export function writeShell(name: string, value: unknown): void {
  try { localStorage.setItem(KEY, JSON.stringify({ ...readAll(), [name]: scrub(value) })); } catch { /* storage full or off */ }
}

import { useSyncExternalStore } from "react";

const noop = () => () => {};
/** False on the server and on the first (hydrating) client render; true after mount. Keeps cache reads out of hydration. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noop, () => true, () => false);
}
