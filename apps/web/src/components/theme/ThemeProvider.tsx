"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { isLagosNight } from "@/lib/lagosSun";

export type Theme = "light" | "dark" | "system" | "sunset";

type ThemeContextValue = {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (theme: Theme) => void;
  toggle: () => void;
};

const STORAGE_KEY = "odoo-custom-theme";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme === "light") return "light";
  if (theme === "dark") return "dark";
  if (typeof window === "undefined") return "light";
  if (theme === "sunset") return isLagosNight() ? "dark" : "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === "light" || stored === "dark" || stored === "system" || stored === "sunset") {
      setThemeState(stored);
    }
  }, []);

  useEffect(() => {
    const next = resolveTheme(theme);
    setResolved(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const apply = () => {
      const next = resolveTheme(theme);
      setResolved(next);
      document.documentElement.classList.toggle("dark", next === "dark");
    };
    if (theme === "sunset") {
      const t = window.setInterval(apply, 60_000);
      return () => window.clearInterval(t);
    }
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [theme]);

  // Touch 118: theme change spreads via a view transition (CSS turns it into a fade under reduced motion).
  const withReveal = (fn: () => void) => {
    const d = typeof document !== "undefined" ? (document as Document & { startViewTransition?: (cb: () => void) => unknown }) : null;
    if (d?.startViewTransition) d.startViewTransition(fn);
    else fn();
  };
  const setTheme = useCallback((value: Theme) => withReveal(() => setThemeState(value)), []);
  const toggle = useCallback(() => {
    withReveal(() =>
      setThemeState((prev) => {
        const current = resolveTheme(prev);
        return current === "dark" ? "light" : "dark";
      }),
    );
  }, []);

  const value = useMemo(
    () => ({ theme, resolved, setTheme, toggle }),
    [theme, resolved, setTheme, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

/** Returns null outside ThemeProvider — for chrome that also mounts on marketing pages. */
export function useThemeOptional() {
  return useContext(ThemeContext);
}

/** Same as useTheme, but null outside a provider (isolated renders). */
export function useThemeMaybe() {
  return useContext(ThemeContext);
}
