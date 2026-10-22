/**
 * UI-S-13 Menus studio-bar helpers. Pure, no React.
 */

export const PAGE_TITLE = "Menus";
export const PAGE_DESCRIPTION =
  "Where each menu sits, what it opens, and who sees it.";

export type MenusGuide = { title: string; why: string; next: string };

export function sanitizeMenusCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function menusHonestyGuide(): MenusGuide {
  return {
    title: "Tree edits stay local until Save the menu.",
    why: "Drag re-parent stages a move. Odoo refuses recursive menus before anything writes.",
    next: "Select a row, edit the detail, then Save the menu. Create menu opens the composer.",
  };
}

export function menusSessionBadge(opts: { unsaved: boolean; empty: boolean }): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (opts.empty) return { label: "Empty", variant: "default" };
  if (opts.unsaved) return { label: "Unsaved", variant: "warning" };
  return { label: "Ready", variant: "default" };
}
