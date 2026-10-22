"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

export type NavDir = "deeper" | "back" | "side";

/** Touch 49: deeper = more path segments under the same root; back = fewer; anything else is sideways. */
export function navDirection(prev: string, next: string): NavDir {
  const a = prev.split("/").filter(Boolean);
  const b = next.split("/").filter(Boolean);
  const shared = (x: string[], y: string[]) => x.every((s, i) => y[i] === s);
  if (b.length > a.length && shared(a, b)) return "deeper";
  if (b.length < a.length && shared(b, a)) return "back";
  return "side";
}

/** Plays a short entrance on route change without remounting the page (state is kept). */
export function PageMove({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const prev = useRef(pathname);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prev.current === pathname) return;
    window.dispatchEvent(new Event("ingenium:route-settled")); // lets a shared-element morph (35) finish
    el.dataset.navDir = navDirection(prev.current, pathname);
    prev.current = pathname;
    el.classList.remove("page-move");
    void el.offsetWidth; // restart the animation
    el.classList.add("page-move");
  }, [pathname]);
  return <div ref={ref} className="page-move-host">{children}</div>;
}
