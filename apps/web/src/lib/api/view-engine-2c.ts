import { request } from "./client";
import type { Condition, EngineOp, EngineViewType } from "./view-engine";
import type { Placement } from "./view-engine-2b";

// ---- Builders stage 2c (SPEC section 18) ------------------------------------

export type Screen2c = { model: string; view_type: EngineViewType; view_id?: number | null; ops?: EngineOp[] };
export type Item2c<P = Record<string, unknown>> = { id: string; kind: string; key: string; name: string; payload: P; created_at: string | null };

export type DepGroup = { kind: string; title: string; risk: "high" | "medium" | "low"; count: number; items: Array<{ name: string; detail: string; node?: string }> };
export type DepsOut = { field: string; label: string; verdict: string; level: "safe" | "caution" | "blocked"; groups: DepGroup[]; total: number };
export type RequiredImpactOut = { countable: boolean; text: string; matching?: number; missing?: number; sentence?: string };
export type Blocker = { field: string; label: string; node: string; why: string; missing_now?: number | null };
export type StageBlockers = { value: string | number | null; label: string; always: Blocker[]; at_stage: Blocker[]; depends: Blocker[] };
export type SaveBlockersOut = { stage_field: string | null; stage_label: string; stages: StageBlockers[]; summary: string };
export type Heat = { level: 0 | 1 | 2 | 3 | 4; rate: number; count: number; changes: number | null; label: string };
export type HeatmapOut = { total: number; days: number; heat: Record<string, Heat>; tracked_fields: number; legend: string[]; note: string };
export type SampleOut = { records: Array<Record<string, unknown> & { id: number; display_name: string; __sample: true }>; label: string; note: string };
export type A11yIssue = { node: string; kind: string; text: string; fix_label: string | null; fix: Record<string, unknown> | null; detail?: string };
export type A11yOut = {
  reading_order: Array<{ node: string; say: string; focus: boolean }>;
  tab_order: Array<{ node: string; say: string; n: number }>;
  issues: A11yIssue[];
  summary: string;
  simulations: Array<{ key: string; label: string }>;
};
export type StarterOption = { key: string; label: string; fields_found: number; fields_missing: number; missing_labels: string[]; available: boolean };
export type TourStep = { node: string; title: string; text: string };
export type StepSection = { node: string; kind: "group" | "page"; label: string; fields: number };
export type RoleLayer = { id: number; active: boolean; roles: string[] };
export type ScopedPublishOut = { ok: boolean; layer_view_id: number; version_id: string | null; checked: "compared" | "odoo"; check_note: string };
export type RoleDiff = { a: string; b: string; only_a: Array<{ node: string; label: string; why_not: string }>; only_b: Array<{ node: string; label: string; why_not: string }>; text: string; based_on: string };
export type ABResults = {
  metric: string;
  a: { people: number; records: number; filled: number };
  b: { people: number; records: number; filled: number };
  verdict: "too_few" | "A" | "B" | "unclear" | "same";
  text: string;
  p: number | null;
  role_b: string;
};
export type DashSpec = { kind: "graph" | "pivot"; measures: string[]; rows: string[]; cols?: string[]; interval?: string; chart?: string; stacked?: boolean };
export type DashOptions = {
  measures: Array<{ name: string; label: string; type: string }>;
  groupbys: Array<{ name: string; label: string; type: string }>;
  charts: string[];
  intervals: string[];
  dashboards: Item2c<{ view_id: number; view_type: string; menu_id: number | null }>[];
};
export type DashPreview = { rows: Array<Record<string, number | string> & { label: string; count: number }>; measure_labels: Record<string, string>; empty: boolean; note: string };
export type ApprovalPayload = {
  model: string; view_type: EngineViewType; view_id: number | null; summary: string[]; status: string; requested_by: string;
  identity_verified: boolean; note: string; requested_at: string; decided_by?: string; reason?: string; failure?: string; run_at?: string;
};
export type SchedulePayload = { model: string; view_type: EngineViewType; summary: string[]; run_at: string; status: string; failure?: string; approved: boolean; created_by?: string };
export type WatchPayload = {
  model: string; view_type: EngineViewType; status: string; started_at: string; due: string[]; can_undo: boolean; goes_back_to: string;
  results: Array<{ at: string; ok: boolean; problems: string[] }>;
};
export type DigestOut = {
  screens: Array<{ screen: string; publish: number; undo: number; what: string[] }>;
  published: number; undone: number; pending_approvals: number; scheduled: number; text: string;
  subscription: { to: string; on: boolean; weekday: number; last_sent: string | null } | null;
};
export type CoeditOut = {
  seq: number;
  ops: Array<{ seq: number; editor: string; name: string; op: EngineOp }>;
  others: Array<{ editor_id: string; name: string; selected: string | null }>;
  refused: Array<{ op: EngineOp; by: string; reason: string }>;
};
export type BrandCompany = { id: number; name: string; primary_color?: string | false; secondary_color?: string | false; font?: string | false; external_report_layout_id?: [number, string] | false; can_undo: boolean };
export type FromDocOut = { placements: Placement[]; blocks: unknown[]; dropped: string[]; unclear: string[]; lines: number; note?: string };
export type EmailFinding = { severity: "high" | "medium" | "low"; apps: string; text: string; fix: string };
export type EmailChecksOut = { findings: EmailFinding[]; score: number; size_kb: number; summary: string; checked: string; html: string | null; note: string };

const post = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}), signal });
const eng = (id: string, path: string) => `/api/connections/${id}/views/engine/2c/${path}`;
const rep = (id: string, path: string) => `/api/connections/${id}/reports/engine/2c/${path}`;
const mail = (id: string, path: string) => `/api/connections/${id}/emails/engine/2c/${path}`;
type OpsReq = Screen2c & { ops: EngineOp[]; summary?: string[] };

export const viewEngine2cApi = {
  // Insight tools (read-only)
  fieldDeps: (id: string, screen: Screen2c, field: string, removing = false) => post<DepsOut>(eng(id, "deps"), { ...screen, field, removing }),
  requiredImpact: (id: string, model: string, field: string, condition: Condition | null) =>
    post<RequiredImpactOut>(eng(id, "required-impact"), { model, field, condition }),
  saveBlockers: (id: string, screen: Screen2c) => post<SaveBlockersOut>(eng(id, "save-blockers"), screen),
  heatmap: (id: string, screen: Screen2c, days = 90) => post<HeatmapOut>(eng(id, "heatmap"), { ...screen, days }),
  sampleData: (id: string, screen: Screen2c, count = 3) => post<SampleOut>(eng(id, "sample"), { ...screen, count }),
  a11y: (id: string, screen: Screen2c) => post<A11yOut>(eng(id, "a11y"), screen),
  explainScreen: (id: string, screen: Screen2c) => post<{ steps: TourStep[]; written_by: string }>(eng(id, "explain"), screen),
  // Starters and dashboards
  starters: (id: string, model: string) => post<{ starters: StarterOption[]; note: string }>(eng(id, "starters"), { model }),
  starterCreate: (id: string, body: { model: string; key: string; label: string; make_menu: boolean }) =>
    post<{ ok: boolean; view_id: number; fields_used: number; missing: string[] }>(eng(id, "starters/create"), body),
  dashOptions: (id: string, model: string) => post<DashOptions>(eng(id, "dashboards/options"), { model }),
  dashPreview: (id: string, model: string, spec: DashSpec) => post<DashPreview>(eng(id, "dashboards/preview"), { model, spec }),
  dashCreate: (id: string, body: { model: string; spec: DashSpec; label: string; make_menu: boolean }) =>
    post<{ ok: boolean; view_id: number; action_id: number | null; menu_id: number | null }>(eng(id, "dashboards/create"), body),
  // Roles: step-by-step, compare, layout tests
  stepsOptions: (id: string, screen: Screen2c) => post<{ sections: StepSection[]; existing: RoleLayer[]; note: string }>(eng(id, "steps/options"), screen),
  stepsPublish: (id: string, screen: Screen2c, role: string, sections: string[], progress = false) =>
    post<ScopedPublishOut & { steps: number; role: string }>(eng(id, "steps/publish"), { ...screen, ops: [], role, sections, progress }),
  stepsRemove: (id: string, screen: Screen2c, layer_view_id: number) => post<{ ok: boolean }>(eng(id, "steps/remove"), { ...screen, ops: [], layer_view_id }),
  compareRoles: (id: string, screen: Screen2c, role_a: string, role_b: string) => post<RoleDiff>(eng(id, "compare-roles"), { ...screen, role_a, role_b }),
  abStart: (id: string, body: OpsReq & { role_b: string; metric_field: string; name: string }) =>
    post<ScopedPublishOut & { item_id: string }>(eng(id, "abtest/start"), body),
  abList: (id: string, model: string) => post<{ tests: Item2c<{ status: string; role_b_name: string; metric_label: string; started_at: string }>[] }>(eng(id, "abtest/list"), { model }),
  abResults: (id: string, item_id: string) => post<ABResults>(eng(id, "abtest/results"), { item_id }),
  abStop: (id: string, item_id: string) => post<{ ok: boolean; final: ABResults | null }>(eng(id, "abtest/stop"), { item_id }),
  // Publishing: approvals, schedules, watch, digest
  approvalPolicy: (id: string) => post<{ required: boolean; you: string | null; identity_verified: boolean; note: string | null }>(eng(id, "approvals/policy/get"), {}),
  setApprovalPolicy: (id: string, required: boolean) => post<{ ok: boolean; required: boolean }>(eng(id, "approvals/policy"), { required }),
  approvalRequest: (id: string, body: OpsReq & { note: string; base_layer_hash?: string | null }) =>
    post<{ ok: boolean; item_id: string }>(eng(id, "approvals/request"), body),
  approvals: (id: string, model?: string) => post<{ approvals: Item2c<ApprovalPayload>[] }>(eng(id, "approvals/list"), { model: model ?? null }),
  approvalDecide: (id: string, item_id: string, approve: boolean, reason = "", run_at: string | null = null) =>
    post<{ ok: boolean; status: string; run_at?: string }>(eng(id, "approvals/decide"), { item_id, approve, reason, run_at }),
  scheduleCreate: (id: string, body: OpsReq & { run_at: string }) => post<{ ok: boolean; item_id: string; run_at: string }>(eng(id, "schedule/create"), body),
  schedules: (id: string, model?: string) => post<{ scheduled: Item2c<SchedulePayload>[] }>(eng(id, "schedule/list"), { model: model ?? null }),
  scheduleCancel: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "schedule/cancel"), { item_id }),
  watchStart: (id: string, body: { model: string; view_type: EngineViewType; view_id?: number | null; version_id: string }) =>
    post<{ ok: boolean; item_id: string | null }>(eng(id, "watch/start"), body),
  watches: (id: string, model?: string) => post<{ watches: Item2c<WatchPayload>[] }>(eng(id, "watch/list"), { model: model ?? null }),
  watchCheck: (id: string, item_id: string) => post<{ ok: boolean; problems: string[]; status: string }>(eng(id, "watch/check"), { item_id }),
  watchUndo: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "watch/undo"), { item_id }),
  digestPreview: (id: string, days = 7) => post<DigestOut>(eng(id, "digest/preview"), { days }),
  digestSubscribe: (id: string, to: string, on: boolean, weekday = 0) =>
    post<{ ok: boolean; on: boolean; to: string; delivery: string }>(eng(id, "digest/subscribe"), { to, on, weekday }),
  // Live co-editing
  coedit: (id: string, body: Screen2c & { editor_id: string; name: string; selected: string | null; since: number; base_seq: number; ops: EngineOp[] }, signal?: AbortSignal) =>
    post<CoeditOut>(eng(id, "coedit"), body, signal),
  // Reports and emails
  brandCompanies: (id: string) => post<{ companies: BrandCompany[]; note: string }>(rep(id, "brand/companies"), {}),
  brandCopy: (id: string, from_company_id: number, to_company_ids: number[]) =>
    post<{ results: Array<{ company_id: number; ok: boolean; error?: string }>; copied: Record<string, unknown> }>(rep(id, "brand/copy"), { from_company_id, to_company_ids }),
  reportFromDocument: (id: string, report_id: number, filename: string, content_b64: string) =>
    post<FromDocOut>(rep(id, "from-document"), { report_id, filename, content_b64 }),
  emailAppChecks: (id: string, template_id: number, record_id: number | null) => post<EmailChecksOut>(mail(id, "checks"), { template_id, record_id }),
};
