"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { testCopyStatus } from "@/components/ui/craft";

/** Q2 touch 92: confirmations name the database and environment they act on. */
export type ConfirmTarget = { name: string; environment: "Live" | "Test copy"; certain: boolean };

const cache = new Map<string, Promise<ConfirmTarget | null>>();

/** Forget a cached target after its flag changes on Connect. */
export function forgetConfirmTarget(id: string) {
  cache.delete(id);
}

export function connectionIdFromPath(path: string | null): string | null {
  const m = path?.match(/^\/connections\/([^/]+)/);
  return m && m[1] !== "new" ? decodeURIComponent(m[1]) : null;
}

export function useConfirmTarget(open: boolean): ConfirmTarget | null {
  const [t, setT] = useState<ConfirmTarget | null>(null);
  useEffect(() => {
    // Read the path when opened (works without router mocks; dialogs open after navigation settles).
    const id = connectionIdFromPath(typeof window !== "undefined" ? window.location.pathname : null);
    if (!open || !id) return setT(null);
    let alive = true;
    if (!cache.has(id)) {
      cache.set(id, api.getConnection(id).then(
        (c) => {
          const st = testCopyStatus(c);
          return { name: c.name || c.db_name || "this database", environment: st.test ? "Test copy" : "Live", certain: st.certain } as ConfirmTarget;
        },
        () => null,
      ));
    }
    void cache.get(id)!.then((v) => alive && setT(v));
    return () => {
      alive = false;
    };
  }, [open]);
  return t;
}
