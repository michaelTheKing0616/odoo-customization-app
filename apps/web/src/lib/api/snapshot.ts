import { request, ODOO_RPC_READ_TIMEOUT_MS } from "./client";

/** Read-only, metadata-only picture of the connected database (GET /snapshot). */
export type SnapshotAvailability = "yes" | "no" | "verify" | "plan_gated";

export type LiveSnapshot = {
  ok: boolean;
  major: number;
  series: string;
  server_version: string;
  edition: "community" | "enterprise" | "unknown";
  hosting: "online" | "sh" | "onprem" | "unknown";
  support: string;
  apps: { name: string; label: string }[];
  modules: string[];
  counts: {
    modules: number;
    modules_hidden: number;
    apps: number;
    models: number;
    custom_models: number;
    automations: number;
    scheduled_actions: number;
    groups: number;
  };
  custom_models: { model: string; label: string }[];
  models: { model: string; label: string }[];
  automations: Record<string, string>[];
  scheduled_actions: Record<string, string>[];
  groups: { name: string; category: string }[];
  can_change: { key: string; available: SnapshotAvailability; reason: string }[];
  problems: string[];
  attention: AttentionItem[];
};

export type AttentionSeverity = "critical" | "warning" | "limit" | "notice";

/** Ranked "needs attention" item. Drill targets point at an Overview section or explorer tab. */
export type AttentionItem = {
  key: string;
  severity: AttentionSeverity;
  rank: number;
  title: string;
  detail: string;
  count: number;
  names: string[];
  drill: { section: OverviewSectionId; model?: string; tab?: ExplorerTab };
};

export type OverviewSectionId = "header" | "apps" | "custom-models" | "automations" | "capabilities" | "explorer";
export type ExplorerTab = "fields" | "views" | "rules" | "actions" | "menus";

export type SnapshotModelDetail = {
  model: string;
  label: string;
  custom: boolean;
  fields: {
    name: string;
    type: string;
    string: string;
    required: boolean;
    relation: string;
    selection: string[];
      /** Set for custom (x_) fields: ir.model.fields id, so the Overview can edit them. */
    custom?: boolean;
    id?: number | null;
    help?: string;
  }[];
  views: { types: string[]; form_field_count: number; form_fields: string[] };
  server_actions: { name: string; kind: string }[];
  record_rules: {
    source: "ir.rule" | "ir.access";
    rows: { name: string; group: string; operation: string; domain: string; kind: string }[];
    access?: { name: string; group: string; operation: string }[];
  };
  menus: string[];
  problems: string[];
};

export const snapshotApi = {
  /** ``refresh`` drops this connection's cached snapshot first (use after an Apply). */
  getLiveSnapshot: (id: string, opts: { refresh?: boolean } = {}) =>
    request<LiveSnapshot>(`/api/connections/${id}/snapshot${opts.refresh ? "?refresh=true" : ""}`, {
      timeoutMs: ODOO_RPC_READ_TIMEOUT_MS,
    }),
  getSnapshotModel: (id: string, model: string, opts: { refresh?: boolean } = {}) =>
    request<SnapshotModelDetail>(
      `/api/connections/${id}/snapshot/models/${encodeURIComponent(model)}${opts.refresh ? "?refresh=true" : ""}`,
      { timeoutMs: ODOO_RPC_READ_TIMEOUT_MS },
    ),
};
