import { fetchApi, formatDetailMessage, request } from "./client";
import type { EngineOp } from "./view-engine";
import type { Screen2c } from "./view-engine-2c";

const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const eng = (id: string, path: string) => `/api/connections/${id}/views/engine/2d/${path}`;
const rep = (id: string, path: string) => `/api/connections/${id}/reports/engine/2d/${path}`;
const mail = (id: string, path: string) => `/api/connections/${id}/emails/engine/2d/${path}`;

export type Change2d = { kind: "added" | "removed" | "changed" | "moved"; node: string; text: string };
export type TileSpec = { model: string; measure: string; date_field: string; period: "week" | "month" | "quarter"; label?: string };
export type TileOut = { id?: string; label: string; value?: number; previous?: number; change?: string; period?: string; error?: string };
export type Comment2d = { id: string; payload: { node: string; text: string; by: string; at: string } };
export type BrandPreset = { id: string; name: string; payload: { primary_color: string | null; secondary_color: string | null; font: string | null; layout_xmlid: string | null } };
export type Outline2d = { node: string; tag: string; label: string; hidden: boolean }[];
export type Compare2d = {
  source: { major: number; items: Outline2d };
  target_now: { major: number; items: Outline2d };
  target_after: { items: Outline2d };
  changes: Change2d[];
  still_different: Change2d[];
  problems: string[];
  replaces: boolean;
  note: string;
};
export type Delivery = { status: "sent" | "queued" | "failed" | "log_only"; note: string };

export const viewEngine2dApi = {
  approvalDiff: (id: string, item_id: string) => post<{ changes: Change2d[]; note: string }>(eng(id, "approvals/diff"), { item_id }),
  approvers: (id: string) => post<{ approvers: Record<string, string[]> }>(eng(id, "approvals/approvers/get")),
  setApprovers: (id: string, approvers: Record<string, string[]>) => post<{ approvers: Record<string, string[]> }>(eng(id, "approvals/approvers"), { approvers }),
  pauseSet: (id: string, start: string, end: string, reason: string) => post<{ ok: boolean; item_id: string }>(eng(id, "pause/set"), { start, end, reason }),
  pauses: (id: string) => post<{ pauses: { id: string; name: string; payload: { start: string; end: string } }[]; paused_now: boolean; note: string | null }>(eng(id, "pause/list")),
  pauseClear: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "pause/clear"), { item_id }),
  tilePreview: (id: string, spec: TileSpec) => post<TileOut>(eng(id, "tiles/preview"), spec),
  tileSave: (id: string, spec: TileSpec) => post<TileOut & { item_id: string }>(eng(id, "tiles/save"), spec),
  tiles: (id: string) => post<{ tiles: TileOut[] }>(eng(id, "tiles/list")),
  tileDelete: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "tiles/delete"), { item_id }),
  hideUnused: (id: string, s: Screen2c) => post<{ ops: EngineOp[]; labels: string[]; total: number; note: string }>(eng(id, "hide-unused"), { ...s, ops: [] }),
  checklistPublish: (id: string, s: Screen2c) => post<{ ok: boolean; lines: number; role_layouts?: string[] }>(eng(id, "checklist/publish"), { ...s, ops: [] }),
  checklistRemove: (id: string, s: Screen2c) => post<{ ok: boolean }>(eng(id, "checklist/remove"), { ...s, ops: [] }),
  a11yFix: (id: string, s: Screen2c) => post<{ ops: EngineOp[]; why: string[]; note: string }>(eng(id, "a11y/fix"), { ...s, ops: [] }),
  industries: (id: string) => post<{ industries: string[]; note: string }>(eng(id, "sample/industries")),
  industrySample: (id: string, s: Screen2c, industry: string) => post<{ records: Record<string, unknown>[]; label: string; note: string }>(eng(id, "sample"), { ...s, ops: [], industry, count: 1 }),
  digestChat: (id: string, url: string, on = true) => post<{ ok: boolean; kind?: string; url?: string }>(eng(id, "digest/chat"), { url, on }),
  digestChatSend: (id: string) => post<{ ok: boolean; kind: string; status: number; sent_to: string; note: string }>(eng(id, "digest/chat/send-now")),
  digestSendNow: (id: string) => post<Delivery & { to: string }>(`/api/connections/${id}/views/engine/2c/digest/send-now`),
  comments: (id: string, s: Screen2c) => post<{ comments: Comment2d[]; resolved: number }>(eng(id, "comments/list"), { ...s, ops: [] }),
  commentAdd: (id: string, s: Screen2c, node: string, text: string) => post<{ ok: boolean }>(eng(id, "comments/add"), { ...s, ops: [], node, text }),
  commentResolve: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "comments/resolve"), { item_id }),
  promote: (id: string, s: Screen2c, target_connection_id: string, replace = false) =>
    post<{ ok: boolean; target: string; note: string }>(eng(id, "promote"), { ...s, ops: [], target_connection_id, replace }),
  promoteCompare: (id: string, s: Screen2c, target_connection_id: string) => post<Compare2d>(eng(id, "promote/compare"), { ...s, ops: [], target_connection_id }),
  requestAction: (id: string, action: "checklist_publish" | "steps_publish" | "abtest_start" | "abtest_stop", payload: Record<string, unknown>, summary: string[]) =>
    post<{ ok: boolean; item_id: string; status: string }>(`/api/connections/${id}/views/engine/2c/approvals/request-action`, { action, payload, summary }),
  abEvaluate: (id: string, item_id: string) => post<{ ended: boolean; why: string }>(eng(id, "abtest/evaluate"), { item_id }),
  explainExport: async (id: string, s: Screen2c, lang: string) => {
    const res = await fetchApi(eng(id, "explain/export"), { method: "POST", body: JSON.stringify({ ...s, ops: [], lang }) });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const parsed = await res.json();
        detail = parsed.detail ?? parsed;
      } catch {
        /* ignore */
      }
      throw new Error(formatDetailMessage(detail) || "The guide couldn't be made.");
    }
    return { blob: await res.blob(), pdf: (res.headers.get("content-type") ?? "").includes("pdf") };
  },
  presetSave: (id: string, company_id: number, name: string) => post<{ ok: boolean }>(rep(id, "brand/presets/save"), { company_id, name }),
  presets: (id: string) => post<{ presets: BrandPreset[] }>(rep(id, "brand/presets/list")),
  presetApply: (id: string, item_id: string, company_id: number) => post<{ skipped: string[] }>(rep(id, "brand/presets/apply"), { item_id, company_id }),
  emailTestSend: (id: string, template_id: number, record_id: number, to: string) => post<Delivery & { to: string }>(mail(id, "test-send"), { template_id, record_id, to }),
};
