import { request } from "./client";

export type BGConnector = {
  key: string; name: string; category: string; auth: string[]; entities: string[];
  webhook_signature: string | null; health_probe: string; money: boolean; secret_fields: string[]; status: "available" | "template";
};
export type BGAuthStep = { kind: string; step: string; refresh?: boolean; fields?: string[]; signature?: string | null };
export type BGDetail = BGConnector & {
  auth_plan: { steps: BGAuthStep[]; vault_fields: string[]; money_guard: boolean };
  stored: { name: string; set_at: number | null }[]; live_check: boolean;
};
export type BGHealth = {
  connector: string; status: "ok" | "warn" | "fail"; issues: string[]; warnings: string[];
  rate_limit: { limit: number; remaining: number } | null; money_guard: boolean;
  odoo?: { ok: boolean; version?: string; partners?: number; error?: string };
};

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const bridgeGalleryApi = {
  list: (category?: string, q?: string) => {
    const p = new URLSearchParams();
    if (category) p.set("category", category);
    if (q) p.set("q", q);
    return request<{ connectors: BGConnector[]; categories: string[] }>(`/api/bridge/gallery?${p}`);
  },
  get: (key: string) => request<BGDetail>(`/api/bridge/gallery/${key}`),
  saveSecrets: (key: string, values: Record<string, string>) => post<{ ok: boolean; stored: string[] }>(`/api/bridge/gallery/${key}/secrets`, { values }),
  forget: (key: string) => request<{ deleted: boolean }>(`/api/bridge/gallery/${key}/secrets`, { method: "DELETE" }),
  health: (key: string, body: { needed_entities?: string[]; odoo_connection_id?: string | null }) =>
    post<BGHealth>(`/api/bridge/gallery/${key}/health`, body),
};

export type BGSpecEntity = { read: string | null; create: string | null; update: string | null; fields: Record<string, string> };
export type BGSpec = { source: string; name: string; base_url: string; auth: string[]; entities: Record<string, BGSpecEntity>; checks: string[] };
export type BGMapRow = { remote: string; odoo: string | null; confidence: number; transform: string; money?: boolean; needs_review?: boolean };
export type BGMapOut = {
  mapping: BGMapRow[]; errors: string[]; transforms: string[];
  preview: { values: Record<string, unknown>; problems: string[] }[];
  odoo_fields: Record<string, { type: string; string: string; required: boolean }>;
};

export const bridgeBuildApi = {
  importSpec: (text: string, hint?: string) => post<BGSpec>("/api/bridge/import-spec", { text, hint }),
  mapping: (body: { odoo_connection_id: string; model: string; remote_fields: Record<string, string>; samples?: Record<string, unknown>[]; mapping?: BGMapRow[] }) =>
    post<BGMapOut>("/api/bridge/mapping/suggest", body),
};

export type BGTestBody = { odoo_connection_id: string; model: string; remote_fields: Record<string, string>; mapping: BGMapRow[]; samples: Record<string, unknown>[] };
export type BGTests = { ok: boolean; mapping_errors: string[]; cases: { sample: number; ok: boolean; problems: string[] }[] };
export type BGSandbox = { writes: 0; tests: BGTests; counts: { create: number; link: number; review: number }; ready_for_live: boolean;
  plan: { values: Record<string, unknown>; would: string; why?: string }[] };
export const bridgeTestApi = {
  contractTests: (b: BGTestBody) => post<BGTests>("/api/bridge/contract-tests", b),
  sandbox: (b: BGTestBody) => post<BGSandbox>("/api/bridge/sandbox-run", b),
};

export type BGVersion = { n: number; hash: string; status: string; money: boolean; by?: string | null; at?: number };
export type BGFlowSummary = { id: string; live: number | null; candidate: number | null; rollout: number; versions: BGVersion[] };
export type BGCanvas = { nodes: { id: string; kind: string; label: string; x: number; y: number }[]; edges: { from: string; to: string }[] };
export type BGMonitor = { counts: Record<string, number>; volume?: number[]; error_rate: number; last_error: { record: string; detail: string } | null };
export const bridgeFlowsApi = {
  list: () => request<{ flows: BGFlowSummary[] }>("/api/bridge/flows"),
  get: (id: string) => request<BGFlowSummary & { monitor: BGMonitor }>(`/api/bridge/flows/${encodeURIComponent(id)}`),
  canvas: (id: string) => request<BGCanvas>(`/api/bridge/flows/${encodeURIComponent(id)}/canvas`),
  approve: (id: string, n: number, hash: string, approverName?: string) => post<{ status: string; approved_by?: string | null; verified?: boolean }>(`/api/bridge/flows/${encodeURIComponent(id)}/approve`, approverName ? { n, hash, approver_name: approverName } : { n, hash }),
  rollout: (id: string, n: number, percent: number) => post<{ live: number | null }>(`/api/bridge/flows/${encodeURIComponent(id)}/rollout`, { n, percent }),
  rollback: (id: string) => post<{ live: number | null }>(`/api/bridge/flows/${encodeURIComponent(id)}/rollback`, {}),
  trace: (id: string, key: string) => request<{ events: { at: number; step: string; status: string; detail: string }[] }>(`/api/bridge/flows/${encodeURIComponent(id)}/trace/${encodeURIComponent(key)}`),
  exportUrl: (id: string, kind: "service" | "module", major = 18) => `/api/bridge/flows/${encodeURIComponent(id)}/export?kind=${kind}&major=${major}`,
};
