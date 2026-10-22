import { useSyncExternalStore } from "react";

/** Set when Odoo refused a change because the connection is read-only (Observer mode). */
let blocked = false;
const subs = new Set<() => void>();

export function isObserverRefusal(err: unknown): boolean {
  const d = err && typeof err === "object" ? (err as { detail?: unknown }).detail : null;
  return !!d && typeof d === "object" && (d as { error?: unknown }).error === "observer_mode";
}

export function noteWriteRefusal(err: unknown): void {
  if (isObserverRefusal(err) && !blocked) {
    blocked = true;
    subs.forEach((f) => f());
  }
}

export function clearWriteRefusal(): void {
  blocked = false;
  subs.forEach((f) => f());
}

export function useWriteRefused(): boolean {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => void subs.delete(f);
    },
    () => blocked,
    () => false,
  );
}
