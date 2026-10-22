"use client";

import { useCallback, useEffect, useState } from "react";
import type { ExplorerTab } from "@/lib/api";

const TABS: ExplorerTab[] = ["fields", "views", "rules", "actions", "menus"];
export type ExplorerUrl = { model: string | null; tab: ExplorerTab };

function read(): ExplorerUrl {
  if (typeof window === "undefined") return { model: null, tab: "fields" };
  const p = new URLSearchParams(window.location.search);
  const tab = p.get("tab") as ExplorerTab | null;
  return { model: p.get("model") || null, tab: tab && TABS.includes(tab) ? tab : "fields" };
}

/**
 * Explorer selection lives in ?model=&tab= so it reloads and shares.
 * Opening a model pushes a history entry (Back returns to the previous model);
 * switching tabs replaces it (Back doesn't walk through every tab click).
 */
export function useExplorerUrl() {
  const [state, setState] = useState<ExplorerUrl>({ model: null, tab: "fields" });
  useEffect(() => {
    setState(read());
    const onPop = () => setState(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const set = useCallback((next: ExplorerUrl, mode: "push" | "replace") => {
    const p = new URLSearchParams(window.location.search);
    if (next.model) p.set("model", next.model); else p.delete("model");
    if (next.model && next.tab !== "fields") p.set("tab", next.tab); else p.delete("tab");
    const qs = p.toString();
    const url = `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`;
    if (mode === "push") window.history.pushState(window.history.state, "", url);
    else window.history.replaceState(window.history.state, "", url);
    setState(next);
  }, []);
  return { ...state, set };
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Arrival cue: a soft teal tint that fades out over ~1s (playbook §6: exits ease-out),
 * so the eye lands on the drill target. Skipped entirely under prefers-reduced-motion.
 */
export function goToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const reduce = prefersReducedMotion();
  el.scrollIntoView?.({ behavior: reduce ? "auto" : "smooth", block: "start" });
  if (reduce) return;
  el.classList.remove("overview-arrive");
  void el.offsetWidth; // restart the animation on repeat drills
  el.classList.add("overview-arrive");
  el.setAttribute("data-flash", "true");
  const done = () => {
    el.classList.remove("overview-arrive");
    el.removeAttribute("data-flash");
  };
  el.addEventListener("animationend", done, { once: true });
  window.setTimeout(done, 1200); // fallback when animationend never fires
}
