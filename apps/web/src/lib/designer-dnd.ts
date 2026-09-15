/**
 * HTML5 DnD helpers for View Designer.
 * Keep MIME keys stable — palette, canvas reorder, and overlay drop all share them.
 */

export const ODOO_FIELD_MIME = "text/odoo-field";
export const ODOO_CANVAS_FIELD_MIME = "text/odoo-canvas-field";

export type DesignerDragKind = "palette" | "canvas";

export type DesignerDragPayload = {
  kind: DesignerDragKind;
  fieldName?: string;
  fieldId?: string;
};

export function setPaletteDragData(dt: DataTransfer, fieldName: string): void {
  dt.setData(ODOO_FIELD_MIME, fieldName);
  dt.setData("text/plain", fieldName);
  dt.effectAllowed = "copy";
}

export function setCanvasFieldDragData(dt: DataTransfer, fieldId: string, fieldName?: string): void {
  dt.setData(ODOO_CANVAS_FIELD_MIME, fieldId);
  if (fieldName) dt.setData(ODOO_FIELD_MIME, fieldName);
  dt.setData("text/plain", fieldName || fieldId);
  dt.effectAllowed = "move";
}

export function readPaletteFieldName(
  dt: DataTransfer | null | undefined,
  fallback?: string | null,
): string | null {
  const fromMime = dt?.getData(ODOO_FIELD_MIME)?.trim();
  if (fromMime) return fromMime;
  const fromPlain = dt?.getData("text/plain")?.trim();
  if (fromPlain) return fromPlain;
  return fallback?.trim() || null;
}

export function readCanvasFieldId(dt: DataTransfer | null | undefined): string | null {
  return dt?.getData(ODOO_CANVAS_FIELD_MIME)?.trim() || null;
}

export function isPaletteDrag(dt: DataTransfer | null | undefined): boolean {
  if (!dt) return false;
  const types = Array.from(dt.types || []);
  return types.includes(ODOO_FIELD_MIME) && !types.includes(ODOO_CANVAS_FIELD_MIME);
}

export function isCanvasFieldDrag(dt: DataTransfer | null | undefined): boolean {
  if (!dt) return false;
  return Array.from(dt.types || []).includes(ODOO_CANVAS_FIELD_MIME);
}

/**
 * Insertion index from pointer Y against a list of item rects.
 * Returns 0..length (append when below the last midpoint).
 */
export function insertIndexFromClientY(
  clientY: number,
  rects: Array<{ top: number; height: number }>,
): number {
  for (let i = 0; i < rects.length; i += 1) {
    const rect = rects[i];
    if (clientY < rect.top + rect.height / 2) return i;
  }
  return rects.length;
}

export function insertIndexFromElements(clientY: number, elements: ArrayLike<Element>): number {
  const rects: Array<{ top: number; height: number }> = [];
  for (let i = 0; i < elements.length; i += 1) {
    const el = elements[i];
    if (!(el instanceof HTMLElement)) continue;
    const r = el.getBoundingClientRect();
    rects.push({ top: r.top, height: r.height });
  }
  return insertIndexFromClientY(clientY, rects);
}

export function insertAt<T>(list: T[], index: number, item: T): T[] {
  const i = Math.max(0, Math.min(index, list.length));
  const next = list.slice();
  next.splice(i, 0, item);
  return next;
}

export function moveItem<T>(list: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex < 0 || fromIndex >= list.length) return list;
  const next = list.slice();
  const [item] = next.splice(fromIndex, 1);
  const dest = Math.max(0, Math.min(toIndex > fromIndex ? toIndex - 1 : toIndex, next.length));
  next.splice(dest, 0, item);
  return next;
}

/** Build a lightweight drag ghost so the native image isn't a raw list row. */
export function attachDragGhost(
  dt: DataTransfer,
  label: string,
  owner: HTMLElement,
): HTMLElement | null {
  if (typeof document === "undefined") return null;
  const ghost = document.createElement("div");
  ghost.className = "designer-drag-ghost";
  ghost.textContent = label;
  ghost.setAttribute("aria-hidden", "true");
  owner.appendChild(ghost);
  dt.setDragImage(ghost, 16, 16);
  window.requestAnimationFrame(() => {
    ghost.remove();
  });
  return ghost;
}
