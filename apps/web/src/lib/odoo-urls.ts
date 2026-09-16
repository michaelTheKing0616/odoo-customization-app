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
  | "cohort"
  | "grid";

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
 * Deep-link a specific record. Odoo 19 hash routing ignores a trailing `id=`
 * without an invoice window action and lands on the Invoicing app list.
 * Prefer `/odoo/action-<id>/<recordId>` when the act_window is known.
 */
export function odooRecordUrl(
  baseUrl: string,
  model: string,
  recordId: number,
  actionId?: number | null,
): string {
  const root = baseUrl.replace(/\/$/, "");
  if (recordId > 0 && actionId && actionId > 0) {
    return `${root}/odoo/action-${actionId}/${recordId}`;
  }
  if (recordId > 0) {
    const params = new URLSearchParams();
    params.set("id", String(recordId));
    params.set("model", model);
    params.set("view_type", "form");
    return `${root}/web#${params.toString()}`;
  }
  return odooViewUrl(baseUrl, model, "form", actionId, recordId);
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
  recordId?: number | null,
): string {
  const root = baseUrl.replace(/\/$/, "");
  const vt = viewType === "tree" ? "list" : viewType;
  // Odoo 19 SPA: action path is reliable; bare model= often lands on Discuss.
  if (actionId && actionId > 0 && !(recordId && recordId > 0)) {
    return `${root}/odoo/action-${actionId}`;
  }
  if (recordId && recordId > 0 && actionId && actionId > 0) {
    return `${root}/odoo/action-${actionId}/${recordId}`;
  }
  const params = new URLSearchParams();
  if (actionId && actionId > 0) {
    params.set("action", String(actionId));
  }
  params.set("model", model);
  params.set("view_type", vt);
  if (recordId && recordId > 0) {
    params.set("id", String(recordId));
  }
  // Legacy hash form — Odoo 19 still accepts and converts to /odoo/…
  return `${root}/web#${params.toString()}`;
}

/**
 * Prefer Quotations / stock list actions over related smart-button windows.
 */
export function preferHostListActionId(
  rows: WindowActionCandidate[],
  hostModel: string,
): number | null {
  const standalone = rows.filter((r) => !actionRequiresActiveId(r));
  const pool = standalone.length ? standalone : rows;
  if (!pool.length) return null;
  const prefer =
    hostModel === "sale.order"
      ? /quotation/i
      : hostModel === "account.move"
        ? /invoice|bill/i
        : hostModel === "purchase.order"
          ? /request\s+for\s+quotation|rfq|purchase\s+order/i
          : null;
  if (prefer) {
    const hit = pool.find((r) => prefer.test(String(r.name || "")));
    if (hit?.id) return hit.id;
  }
  return pickStandaloneWindowAction(pool, "list");
}

/**
 * Open the app root in Odoo (home-grid click / selectMenu).
 * Legacy hash — Odoo 19 still accepts and converts to /odoo/…
 */
export function odooMenuUrl(
  baseUrl: string,
  menuId: number,
  actionId?: number | null,
): string {
  const root = baseUrl.replace(/\/$/, "");
  const params = new URLSearchParams();
  params.set("menu_id", String(menuId));
  if (actionId && actionId > 0) {
    params.set("action", String(actionId));
  }
  return `${root}/web#${params.toString()}`;
}

const LOCAL_SANDBOX_HOSTS = new Set([
  "127.0.0.1",
  "localhost",
  "0.0.0.0",
  "host.docker.internal",
]);

/** Match API `is_local_docker_connection` — unattended Autopilot sandbox. */
export function isLocalSandboxUrl(url: string, port = 8069): boolean {
  try {
    const parsed = new URL(url.includes("://") ? url : `http://${url}`);
    const host = (parsed.hostname || "").toLowerCase();
    const p = parsed.port
      ? Number(parsed.port)
      : parsed.protocol === "https:"
        ? 443
        : 80;
    return LOCAL_SANDBOX_HOSTS.has(host) && p === port;
  } catch {
    return false;
  }
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

/** Open-in-Odoo for a Day-1 checklist row. Human path hints stay text, not URLs. */
export function checklistOpenHref(
  item: {
    action_id?: number | null;
    odoo_model?: string;
    href_hint?: string;
  },
  baseUrl?: string | null,
): string | null {
  const root = (baseUrl || "").replace(/\/$/, "");
  if (!root) return null;
  if (item.action_id && item.action_id > 0) {
    return odooViewUrl(root, item.odoo_model || "ir.ui.menu", "list", item.action_id);
  }
  if (item.odoo_model) {
    return odooViewUrl(root, item.odoo_model, "list");
  }
  const hint = item.href_hint || "";
  if (hint.startsWith("/web#")) {
    return `${root}${hint}`;
  }
  return null;
}

export type GoldInspectLink = {
  href: string;
  label: string;
  hint: string;
};

/** Connected Odoo inspect target after Option A gold Promote — never General Settings. */
export function goldOptionAInspectLink(
  goldId: string | null | undefined,
  baseUrl: string | null | undefined,
  opts?: { hostReady?: boolean; actionId?: number | null; href?: string | null },
): GoldInspectLink | null {
  if (opts?.hostReady !== true) return null;
  const id = (goldId || "").trim();
  const cbnHint =
    "Invoicing → Configuration → Settings on this connection. Do not use Settings → search Currency — that is the Enterprise upgrade tease. After Promote: Automatic Currency Rates → Central Bank of Nigeria → Update now, then Currencies → USD → Rates.";
  if (opts.href) {
    const label =
      id === "currency_rate_cbn"
        ? "Open Accounting Settings"
        : id === "pos_receipt_options"
          ? "Open Point of Sale"
          : id === "invoice_qweb"
            ? "Open Invoices"
            : "Open connected Odoo";
    return {
      href: opts.href,
      label,
      hint: id === "currency_rate_cbn" ? cbnHint : "This connection’s Odoo — not the ephemeral sandbox.",
    };
  }
  const root = (baseUrl || "").replace(/\/$/, "");
  if (!root) return null;
  if (id === "currency_rate_cbn") {
    if (!opts.actionId) return null;
    return {
      href: odooViewUrl(root, "res.config.settings", "form", opts.actionId),
      label: "Open Accounting Settings",
      hint: cbnHint,
    };
  }
  if (id === "pos_receipt_options") {
    return {
      href: odooViewUrl(root, "pos.config", "list", opts.actionId),
      label: "Open Point of Sale",
      hint: "This connection’s Odoo. After Promote: open a POS config and check receipt header/footer.",
    };
  }
  if (id === "invoice_qweb") {
    return {
      href: odooViewUrl(root, "account.move", "list", opts.actionId),
      label: "Open Invoices",
      hint: "This connection’s Odoo. After Promote: print a customer invoice PDF.",
    };
  }
  return {
    href: `${root}/web`,
    label: "Open connected Odoo",
    hint: "Sandbox install does not stay up. Promote first, then inspect this connection.",
  };
}
