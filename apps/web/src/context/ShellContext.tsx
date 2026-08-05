"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ShellUiContext = {
  route?: string;
  model?: string;
  draftSummary?: string;
  viewType?: string;
  triggerType?: string;
};

export type ExpertPrefill = {
  question: string;
  errorText?: string;
  /** Submit immediately when the panel opens (diagnose-from-error flow). */
  autoSubmit?: boolean;
  /** Ignore prior Expert turns so diagnosis is not polluted by old context. */
  freshThread?: boolean;
};

type ShellContextValue = {
  connectionId: string;
  uiContext: ShellUiContext;
  setUiContext: (patch: Partial<ShellUiContext>) => void;
  contextEnabled: boolean;
  setContextEnabled: (enabled: boolean) => void;
  expertOpen: boolean;
  setExpertOpen: (open: boolean) => void;
  openExpert: (prefill?: ExpertPrefill) => void;
  expertPrefill: ExpertPrefill | null;
  clearExpertPrefill: () => void;
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  commandOpen: boolean;
  setCommandOpen: (open: boolean) => void;
};

const ShellContext = createContext<ShellContextValue | null>(null);

const SIDEBAR_KEY = "odoo-custom-sidebar-collapsed";

export function ShellProvider({
  connectionId,
  children,
}: {
  connectionId: string;
  children: ReactNode;
}) {
  const [uiContext, setUiContextState] = useState<ShellUiContext>({});
  const [contextEnabled, setContextEnabled] = useState(true);
  const [expertOpen, setExpertOpen] = useState(false);
  const [expertPrefill, setExpertPrefill] = useState<ExpertPrefill | null>(null);
  const [sidebarCollapsed, setSidebarCollapsedState] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_KEY);
    if (stored === "1") setSidebarCollapsedState(true);
  }, []);

  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    setSidebarCollapsedState(collapsed);
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  }, []);

  const setUiContext = useCallback((patch: Partial<ShellUiContext>) => {
    setUiContextState((prev) => {
      let changed = false;
      for (const key of Object.keys(patch) as (keyof ShellUiContext)[]) {
        if (prev[key] !== patch[key]) {
          changed = true;
          break;
        }
      }
      if (!changed) return prev;
      return { ...prev, ...patch };
    });
  }, []);

  const openExpert = useCallback((prefill?: ExpertPrefill) => {
    if (prefill) setExpertPrefill(prefill);
    setExpertOpen(true);
  }, []);

  const clearExpertPrefill = useCallback(() => setExpertPrefill(null), []);

  const value = useMemo(
    () => ({
      connectionId,
      uiContext,
      setUiContext,
      contextEnabled,
      setContextEnabled,
      expertOpen,
      setExpertOpen,
      openExpert,
      expertPrefill,
      clearExpertPrefill,
      sidebarCollapsed,
      setSidebarCollapsed,
      commandOpen,
      setCommandOpen,
    }),
    [
      connectionId,
      uiContext,
      setUiContext,
      contextEnabled,
      expertOpen,
      openExpert,
      expertPrefill,
      clearExpertPrefill,
      sidebarCollapsed,
      setSidebarCollapsed,
      commandOpen,
    ],
  );

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell() {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used within ShellProvider");
  return ctx;
}

/** Optional hook for pages outside shell — no-op safe accessors */
export function useShellOptional() {
  return useContext(ShellContext);
}
