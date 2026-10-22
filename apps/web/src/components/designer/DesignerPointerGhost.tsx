"use client";

import { useCallback, type PointerEvent } from "react";

/**
 * Pointer-following drag ghost for ReorderableBlocks rows (UI-F13 stays the
 * only drag stack). It only reads the item's `data-dragging` flag and moves a
 * fixed-position chip with `transform`, written straight to the node so no
 * React render runs per pointer move. Tracking is 1:1, also under reduced motion.
 */
export const GHOST_OFFSET_X = 14;
export const GHOST_OFFSET_Y = 10;

export function ghostTransform(clientX: number, clientY: number): string {
  return `translate3d(${Math.round(clientX + GHOST_OFFSET_X)}px, ${Math.round(clientY + GHOST_OFFSET_Y)}px, 0)`;
}

export function useDesignerPointerGhost() {
  return useCallback((event: PointerEvent<HTMLElement>) => {
    const item = event.currentTarget;
    if (item.getAttribute("data-dragging") !== "true") return;
    const ghost = item.querySelector<HTMLElement>("[data-designer-ghost]");
    if (!ghost) return;
    ghost.style.transform = ghostTransform(event.clientX, event.clientY);
    ghost.setAttribute("data-positioned", "true");
  }, []);
}

export function DesignerPointerGhost({ label, name }: { label: string; name?: string }) {
  return (
    <span className="designer-pointer-ghost" data-designer-ghost="" aria-hidden>
      <span>{label}</span>
      {name && name !== label ? <span className="designer-ghost-name">{name}</span> : null}
    </span>
  );
}

/**
 * Drag handle for a ReorderableBlocks row. A plain span (not a control), so
 * ReorderableBlocks accepts the pointer-down; mousedown is cancelled so a drag
 * never starts a text selection or steals focus from the selected row.
 */
export function DesignerGrip({ testId }: { testId?: string }) {
  return (
    <span
      className="designer-grip"
      aria-hidden
      data-testid={testId}
      onMouseDown={(e) => e.preventDefault()}
    />
  );
}
