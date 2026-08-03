"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { UpgradeSheet } from "@/components/billing/UpgradeSheet";

export type UpgradeContextValue = {
  openUpgrade: (featureKey?: string) => void;
  closeUpgrade: () => void;
};

const UpgradeCtx = createContext<UpgradeContextValue | null>(null);

export function UpgradeProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [featureKey, setFeatureKey] = useState<string | undefined>();

  const openUpgrade = useCallback((key?: string) => {
    setFeatureKey(key);
    setOpen(true);
  }, []);

  const closeUpgrade = useCallback(() => setOpen(false), []);

  const value = useMemo(
    () => ({ openUpgrade, closeUpgrade }),
    [openUpgrade, closeUpgrade],
  );

  return (
    <UpgradeCtx.Provider value={value}>
      {children}
      <UpgradeSheet open={open} onOpenChange={setOpen} featureKey={featureKey} />
    </UpgradeCtx.Provider>
  );
}

export function useUpgrade() {
  const ctx = useContext(UpgradeCtx);
  if (!ctx) {
    return {
      openUpgrade: (_key?: string) => {
        window.location.href = "/pricing";
      },
      closeUpgrade: () => undefined,
    };
  }
  return ctx;
}

/** Parse API 403 feature gate payloads and open upgrade sheet when matched. */
export function maybeOpenUpgradeFromError(err: unknown, openUpgrade: (key?: string) => void): boolean {
  if (!(err instanceof Error)) return false;
  try {
    const parsed = JSON.parse(err.message) as { feature_key?: string; error?: string };
    if (parsed?.error === "feature_gated" || parsed?.feature_key) {
      openUpgrade(parsed.feature_key);
      return true;
    }
  } catch {
    if (err.message.includes("feature_gated") || err.message.includes("active_projects_limit")) {
      openUpgrade();
      return true;
    }
  }
  return false;
}
