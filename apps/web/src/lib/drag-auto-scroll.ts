/**
 * Auto-scroll nearest overflow containers while HTML5 dragging near an edge.
 * Does not fight normal wheel/trackpad scrolling: window scroll is a last resort,
 * and the RAF loop stops if dragover goes idle.
 */

const EDGE_PX = 40;
const MAX_STEP_PX = 18;
const IDLE_MS = 120;

function overflowScrollable(el: HTMLElement, axis: "y" | "x"): boolean {
  const style = window.getComputedStyle(el);
  const overflow = axis === "y" ? style.overflowY : style.overflowX;
  if (!/(auto|scroll|overlay)/.test(overflow)) return false;
  if (axis === "y") return el.scrollHeight > el.clientHeight + 1;
  return el.scrollWidth > el.clientWidth + 1;
}

/** Walk from node upward; collect distinct scrollable ancestors (nearest first). */
export function findScrollableAncestors(start: Element | null): HTMLElement[] {
  const out: HTMLElement[] = [];
  let node: Element | null = start;
  while (node && node !== document.documentElement) {
    if (node instanceof HTMLElement) {
      if (overflowScrollable(node, "y") || overflowScrollable(node, "x")) {
        out.push(node);
      }
    }
    node = node.parentElement;
  }
  return out;
}

function stepForProximity(distanceFromEdge: number): number {
  if (distanceFromEdge >= EDGE_PX || distanceFromEdge < 0) return 0;
  const t = 1 - distanceFromEdge / EDGE_PX;
  return Math.max(1, Math.round(MAX_STEP_PX * t * t));
}

function scrollElementAxis(
  el: HTMLElement,
  axis: "y" | "x",
  client: number,
  start: number,
  end: number,
): boolean {
  if (!overflowScrollable(el, axis)) return false;
  const nearStart = stepForProximity(client - start);
  const nearEnd = stepForProximity(end - client);
  if (axis === "y") {
    if (nearStart && el.scrollTop > 0) {
      el.scrollTop -= nearStart;
      return true;
    }
    if (nearEnd && el.scrollTop + el.clientHeight < el.scrollHeight) {
      el.scrollTop += nearEnd;
      return true;
    }
  } else {
    if (nearStart && el.scrollLeft > 0) {
      el.scrollLeft -= nearStart;
      return true;
    }
    if (nearEnd && el.scrollLeft + el.clientWidth < el.scrollWidth) {
      el.scrollLeft += nearEnd;
      return true;
    }
  }
  return false;
}

/**
 * Scroll the nearest scrollable under the pointer when near that element's edge.
 * Only scrolls the window when no nested scrollable is under the pointer.
 */
export function autoScrollFromPointer(clientX: number, clientY: number): boolean {
  if (typeof document === "undefined") return false;

  const under =
    typeof document.elementFromPoint === "function"
      ? document.elementFromPoint(clientX, clientY)
      : null;
  const candidates = findScrollableAncestors(under);

  // Prefer the innermost overflow box — do not also shove the page.
  for (const el of candidates) {
    const rect = el.getBoundingClientRect();
    const movedY = scrollElementAxis(el, "y", clientY, rect.top, rect.bottom);
    const movedX = scrollElementAxis(el, "x", clientX, rect.left, rect.right);
    if (movedY || movedX) return true;
  }

  // Window fallback only when not over a nested scroller (e.g. empty page chrome).
  if (candidates.length > 0) return false;

  const vh = window.innerHeight;
  const vw = window.innerWidth;
  let scrolled = false;
  const up = stepForProximity(clientY);
  const down = stepForProximity(vh - clientY);
  const left = stepForProximity(clientX);
  const right = stepForProximity(vw - clientX);
  if (up) {
    window.scrollBy(0, -up);
    scrolled = true;
  } else if (down) {
    window.scrollBy(0, down);
    scrolled = true;
  }
  if (left) {
    window.scrollBy(-left, 0);
    scrolled = true;
  } else if (right) {
    window.scrollBy(right, 0);
    scrolled = true;
  }
  return scrolled;
}

function isActiveDrag(e: DragEvent): boolean {
  const types = e.dataTransfer?.types;
  if (!types || types.length === 0) return false;
  // Ignore accidental/empty drags; our designer sets text/odoo-field or text/plain.
  return true;
}

/** Attach document-level dragover auto-scroll. Returns cleanup. */
export function attachDragAutoScroll(): () => void {
  if (typeof document === "undefined") return () => undefined;

  let raf = 0;
  let lastX = 0;
  let lastY = 0;
  let dragging = false;
  let lastDragOverAt = 0;

  const stop = () => {
    dragging = false;
    if (raf) {
      window.cancelAnimationFrame(raf);
      raf = 0;
    }
  };

  const tick = () => {
    raf = 0;
    if (!dragging) return;
    if (Date.now() - lastDragOverAt > IDLE_MS) {
      // Pointer idle / user scrolling with wheel — do not keep shoving the page.
      return;
    }
    autoScrollFromPointer(lastX, lastY);
    raf = window.requestAnimationFrame(tick);
  };

  const onDragStart = (e: DragEvent) => {
    if (!isActiveDrag(e)) return;
    dragging = true;
    lastDragOverAt = Date.now();
  };

  const onDragOver = (e: DragEvent) => {
    if (!dragging && !isActiveDrag(e)) return;
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    lastDragOverAt = Date.now();
    if (!raf) raf = window.requestAnimationFrame(tick);
  };

  const onWheel = () => {
    // User is manually scrolling — pause auto-scroll until the next dragover.
    lastDragOverAt = 0;
  };

  const onEnd = () => stop();

  document.addEventListener("dragstart", onDragStart, true);
  document.addEventListener("dragover", onDragOver, true);
  document.addEventListener("dragend", onEnd, true);
  document.addEventListener("drop", onEnd, true);
  document.addEventListener("wheel", onWheel, { capture: true, passive: true });

  return () => {
    stop();
    document.removeEventListener("dragstart", onDragStart, true);
    document.removeEventListener("dragover", onDragOver, true);
    document.removeEventListener("dragend", onEnd, true);
    document.removeEventListener("drop", onEnd, true);
    document.removeEventListener("wheel", onWheel, true);
  };
}
