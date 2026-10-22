"use client";

import { useCallback, useRef } from "react";

/** Touch 39: fling a side sheet away. Soft resistance the wrong way. */
export function flickOffset(dx: number, dir: 1 | -1): number {
  const toward = dx * dir;
  return toward >= 0 ? dx : (dir * -1) * Math.sqrt(-toward) * 2; // rubber band, grows slowly
}

export function shouldDismiss(dx: number, dir: 1 | -1, width: number, velocity: number): boolean {
  const toward = dx * dir;
  return toward > width * 0.4 || (toward > 24 && velocity * dir > 0.5);
}

function scrollsX(el: Element | null, stop: Element): boolean {
  for (let n = el; n && n !== stop; n = n.parentElement) {
    if (n.scrollWidth > n.clientWidth + 1 && /(auto|scroll)/.test(getComputedStyle(n).overflowX)) return true;
  }
  return false;
}

export function useFlickDismiss(side: "right" | "left", onDismiss: () => void) {
  const dir: 1 | -1 = side === "right" ? 1 : -1;
  const panel = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{ x: number; t: number; lastX: number; lastT: number; id: number } | null>(null);
  const wheel = useRef({ sum: 0, timer: 0 });

  const set = (dx: number, animate: boolean) => {
    const el = panel.current;
    if (!el) return;
    el.style.transition = animate ? "transform 240ms cubic-bezier(0.32,0.72,0,1)" : "none";
    el.style.transform = dx ? `translateX(${dx}px)` : "";
  };

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0 || (e.target as Element).closest("button,a,input,textarea,select,[contenteditable]")) return;
    drag.current = { x: e.clientX, t: e.timeStamp, lastX: e.clientX, lastT: e.timeStamp, id: e.pointerId };
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  }, []);
  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    d.lastX = e.clientX;
    d.lastT = e.timeStamp;
    set(flickOffset(e.clientX - d.x, dir), false);
  }, [dir]);
  const end = useCallback((e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    drag.current = null;
    const dx = e.clientX - d.x;
    const v = (e.clientX - d.x) / Math.max(1, e.timeStamp - d.t);
    const w = panel.current?.offsetWidth ?? 400;
    if (shouldDismiss(dx, dir, w, v)) {
      set(dir * w, true);
      window.setTimeout(onDismiss, 200);
    } else set(0, true);
  }, [dir, onDismiss]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    if (Math.abs(e.deltaX) <= Math.abs(e.deltaY) || !panel.current) return;
    if (scrollsX(e.target as Element, panel.current)) return;
    const w = wheel.current;
    w.sum -= e.deltaX; // trackpad swipe right gives negative deltaX
    window.clearTimeout(w.timer);
    const w0 = panel.current.offsetWidth;
    if (shouldDismiss(w.sum, dir, w0 * 0.5, 0)) {
      w.sum = 0;
      set(dir * w0, true);
      window.setTimeout(onDismiss, 200);
      return;
    }
    set(flickOffset(w.sum, dir), false);
    w.timer = window.setTimeout(() => {
      w.sum = 0;
      set(0, true);
    }, 140);
  }, [dir, onDismiss]);

  return { panel, handle: { onPointerDown, onPointerMove, onPointerUp: end, onPointerCancel: end, style: { touchAction: "pan-y" as const } }, onWheel };
}
