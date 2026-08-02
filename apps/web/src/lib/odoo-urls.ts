/** Odoo deep-link helpers for Designer / Open-in-Odoo. */

export type OdooViewType =
  | "form"
  | "list"
  | "search"
  | "kanban"
  | "tree"
  | "calendar"
  | "graph"
  | "pivot"
  | "map"
  | "activity"
  | "gantt"
  | "cohort";

export type WindowActionCandidate = {
  id: number;
  name?: string;
  view_mode?: string | null;
  domain?: string | null;
  context?: string | null;
  /** Server-computed; if omitted, inferred from domain/context text. */
  requires_active_id?: boolean;
};

/**
 * Related / smart-button window actions embed ``active_id`` in domain or context.
 * Opening them via Designer deep-link (no form record) crashes Odoo 19 with
 * ``Name 'active_id' is not defined``.
 */
export function actionRequiresActiveId(action: WindowActionCandidate): boolean {
  if (action.requires_active_id === true) return true;
  if (action.requires_active_id === false) return false;
  const blob = `${action.domain ?? ""} ${action.context ?? ""}`;
  return /\bactive_ids?\b/.test(blob);
}

/**
 * Prefer a standalone act_window (no active_id) that includes ``viewType``.
 * Never prefer related smart-button actions for Open-in-Odoo.
 */
export function pickStandaloneWindowAction(
  rows: WindowActionCandidate[],
  viewType: OdooViewType | string,
): number | null {
  if (!rows.length) return null;
  const vt = viewType === "tree" ? "list" : viewType;
  const standalone = rows.filter((r) => !actionRequiresActiveId(r));
  const pool = standalone.length > 0 ? standalone : [];
  if (!pool.length) {
    // All candidates need active_id — do not deep-link an action id (caller
    // should fall back to model+view_type only).
    return null;
  }
  const withMode = pool.find((r) => (r.view_mode || "").split(",").map((s) => s.trim()).includes(vt));
  return (withMode ?? pool[0])?.id ?? null;
}

/**
 * Build an Open-in-Odoo URL.
 *
 * Prefer ``actionId`` when known: Odoo 19 path routing often ignores bare
 * ``model=`` + ``view_type=`` and falls back to Discuss/home if the window
 * action's ``view_mode`` does not include that type.
 *
 * Never pass a related action id that requires ``active_id``.
 */
export function odooViewUrl(
  baseUrl: string,
  model: string,
  viewType: OdooViewType = "form",
  actionId?: number | null,
): string {
  const root = baseUrl.replace(/\/$/, "");
  const vt = viewType === "tree" ? "list" : viewType;
  const params = new URLSearchParams();
  if (actionId && actionId > 0) {
    params.set("action", String(actionId));
  }
  params.set("model", model);
  params.set("view_type", vt);
  // Legacy hash form — Odoo 19 still accepts and converts to /odoo/…
  return `${root}/web#${params.toString()}`;
}

export function sameOriginPreviewUrl(
  connectionId: string,
  model: string,
  viewType: OdooViewType,
  apiBase?: string,
): string {
  const vt = viewType === "tree" ? "list" : viewType;
  const prefix = (apiBase || "").replace(/\/$/, "");
  return `${prefix}/api/connections/${connectionId}/preview/frame?model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(vt)}`;
}
