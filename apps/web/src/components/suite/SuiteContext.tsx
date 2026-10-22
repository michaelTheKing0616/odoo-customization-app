"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { suiteApi, type SuiteHome } from "@/lib/api/suite";

type Ctx = { connectionId: string; home: SuiteHome | null; error: string | null; readAt: Date | null; reload: () => void };
const SuiteCtx = createContext<Ctx | null>(null);

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** One read of the database facts for the whole suite: the passport belongs to the database, not to a setting. */
export function SuiteProvider({ connectionId, children }: { connectionId: string; children: ReactNode }) {
  const [home, setHome] = useState<SuiteHome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readAt, setReadAt] = useState<Date | null>(null);
  const reload = useCallback(() => {
    suiteApi.home(connectionId).then(
      (h) => { setHome(h); setError(null); setReadAt(new Date()); },
      (e: unknown) => setError(errText(e)),
    );
  }, [connectionId]);
  useEffect(() => { reload(); }, [reload]);
  return <SuiteCtx.Provider value={{ connectionId, home, error, readAt, reload }}>{children}</SuiteCtx.Provider>;
}

export function useSuite(): Ctx {
  const c = useContext(SuiteCtx);
  if (!c) throw new Error("useSuite outside SuiteProvider");
  return c;
}
