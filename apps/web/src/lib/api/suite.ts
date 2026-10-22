import { fetchApi, formatDetailMessage, request } from "./client";

/** Configuration Suite stage 1 API. Code decides; these types mirror apps/api/app/routers/suite.py. */
const base = (id: string) => `/api/connections/${id}/suite`;
const post = <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const put = <T,>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) });

export type Passport = {
  version: string; major: number; edition: string; hosting: string; database: string; url: string;
  apps: string[]; companies: { id: number; name: string; country: string; currency: string }[];
  languages: string[]; localization: string[];
};
export type SuiteHome = {
  passport: Passport;
  writes: { on: boolean; mode: string; paused: boolean };
  facts: { posted_entries: number; done_moves: number };
  needs_you: { kind: string; text: string; href: string }[];
  recent_runs: { id: string; name: string; state: string; kind: string; started_at: string }[];
};
export type Capability = { key: string; label: string; available: string; reason: string; options: string[] };
export type InspectorField = { name: string; label: string; type: string; relation: string | null; required: boolean; stored: boolean; filled: number | null };
export type ViewLayer = { id: number; name: string; key: string; priority: number; depth: number; mode: string; root: number };
export type Inspector = {
  model: string; records: number; fields: InspectorField[]; links: string[];
  views: { form: ViewLayer[]; list: ViewLayer[] }; access: Record<string, unknown>[];
};
export type CatalogTask = {
  id: string; section: string; section_title: string; num: string; title: string; risk: string; versions: string; edition: string;
  rank: number; rank_label: string; state: "available" | "not_here"; reason: string;
  mechanism: { kind: string; models?: string[]; fields?: string[]; note?: string; source: string };
};
export type StepType = "install" | "country_package" | "setting" | "create" | "update" | "units" | "import" | "remove";
export type PlanStep = {
  id: string; type: StepType; task: string | null; label: string; inputs: Record<string, unknown>; depends_on: string[];
  company_id: number | null; source: { kind: string; ref?: string }; reversibility: "one_way" | "revert" | "remove"; risk: string; rank: number;
};
export type Verdict = "ready" | "no_change" | "needs_input" | "blocked" | "waiting";
export type CheckReport = {
  facts: { posted_entries: number; done_moves: number }; waves: string[][]; errors: string[];
  steps: Record<string, { id: string; verdict: Verdict; message: string; changes: Record<string, unknown> }>;
  counts: Record<Verdict, number>; can_apply: boolean; needs_approval: boolean; threshold: number;
  plan_hash: string; checked_at: string; receipt: string | null; receipt_expires_in_s?: number;
};
export type Plan = {
  id: string; name: string; created_at: string | null;
  payload: {
    kind: "setup" | "undo"; steps: PlanStep[]; waves: string[][]; order_errors: string[]; hash: string; rank_labels: Record<string, string>;
    check: CheckReport | null; approval: Approval | null;
    cannot_undo?: string[]; undo_of?: string;
  };
};
export type RunStepState = "waiting" | "running" | "done" | "failed" | "skipped" | "no_change";
export type Run = {
  id: string; name: string;
  payload: {
    plan_id: string; kind: string; state: "queued" | "running" | "paused" | "stopped" | "done" | "failed"; message?: string;
    started_at: string; finished_at: string | null; paused_on?: string | null;
    waves: { n: number; steps: { id: string; label: string; state: RunStepState; message: string }[] }[];
  };
};
export type Approval = { id: string; status: "pending" | "approved" | "rejected" | string; requested_by?: string; decided_by?: string; decided_at?: string; reason?: string };
export type Policy = { approval_threshold: number; cloud_ai: boolean; cloud_ai_consent_by: string | null };
export type MoneyGuard = { facts: { posted_entries: number; done_moves: number }; rules: { key: string; text: string; allowed_now?: boolean }[]; policy: Policy };

export const suiteApi = {
  home: (id: string) => request<SuiteHome>(`${base(id)}/home`),
  capabilities: (id: string) => request<{ version: string; edition: string; hosting: string; capabilities: Capability[] }>(`${base(id)}/capabilities`),
  inspector: (id: string, model: string) => request<Inspector>(`${base(id)}/inspector/${encodeURIComponent(model)}`),
  catalog: (id: string) => request<{ version: string; major: number; edition: string; counts: { total: number; available: number }; tasks: CatalogTask[] }>(`${base(id)}/setup/catalog`),
  importTargets: (id: string) => request<{ targets: { model: string; label: string; guarded: boolean }[] }>(`${base(id)}/setup/import-targets`),
  policy: (id: string) => request<Policy>(`${base(id)}/setup/policy`),
  setPolicy: (id: string, body: Partial<Pick<Policy, "approval_threshold" | "cloud_ai">>) => put<Policy>(`${base(id)}/setup/policy`, body),
  plans: (id: string) => request<{ plans: { id: string; name: string; kind: string; steps: number; created_at: string }[] }>(`${base(id)}/setup/plans`),
  plan: (id: string, planId: string) => request<Plan>(`${base(id)}/setup/plans/${planId}`),
  createPlan: (id: string, name: string, steps: Partial<PlanStep>[]) => post<Plan>(`${base(id)}/setup/plans`, { name, steps }),
  updatePlan: (id: string, planId: string, name: string, steps: Partial<PlanStep>[]) => put<Plan>(`${base(id)}/setup/plans/${planId}`, { name, steps }),
  check: (id: string, planId: string) => post<CheckReport>(`${base(id)}/setup/plans/${planId}/dry-run`),
  checkEveryVersion: (id: string, planId: string, targets: string[]) => post<EveryVersionReport>(`${base(id)}/setup/plans/${planId}/check-every-version`, { targets }),
  requestApproval: (id: string, planId: string) => post<{ ok: boolean; item_id: string; status: string }>(`${base(id)}/setup/plans/${planId}/request-approval`),
  builderOptions: (id: string) => request<BuilderOptions>(`${base(id)}/setup/builder-options`),
  importPreview: (id: string, body: { filename?: string; content_b64?: string; text?: string; model?: string | null; job?: string | null }) =>
    post<ImportPreview>(`${base(id)}/setup/import/preview`, body),
  run: (id: string, planId: string) => post<Run>(`${base(id)}/setup/plans/${planId}/run`),
  runs: (id: string) => request<{ runs: { id: string; name: string; state: string; kind: string; plan_id: string; started_at: string }[] }>(`${base(id)}/setup/runs`),
  getRun: (id: string, runId: string) => request<Run>(`${base(id)}/setup/runs/${runId}`),
  stop: (id: string, runId: string) => post<Run["payload"]>(`${base(id)}/setup/runs/${runId}/stop`),
  carryOn: (id: string, runId: string) => post<Run>(`${base(id)}/setup/runs/${runId}/continue`, { skip_failed: true }),
  undoPlan: (id: string, runId: string) => post<Plan>(`${base(id)}/setup/runs/${runId}/undo-plan`),
  uploadWorkbook: (id: string, name: string, content_b64: string) =>
    post<{ steps: number; notes: string[]; plan: Plan | null }>(`${base(id)}/setup/workbook`, { name, content_b64 }),
  downloadWorkbook: async (id: string): Promise<Blob> => {
    const res = await fetchApi(`${base(id)}/setup/workbook`);
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try { detail = (await res.json()).detail; } catch { /* keep status text */ }
      throw Object.assign(new Error(formatDetailMessage(detail)), { status: res.status, detail });
    }
    return res.blob();
  },
  money: (id: string) => request<MoneyGuard>(`${base(id)}/safety/money`),
};

export type BuilderOptions = {
  settings: { field: string; label: string; type: "boolean" | "selection"; selection: [string, string][]; value: unknown }[];
  units: string[]; categories: string[];
};
export type ImportQuestion = { column: string; question: string; options: { field: string; label: string }[]; can_skip: boolean };
export type ImportTable = {
  table: number; name: string; headers: string[]; row_count: number; sample: string[][]; rows: string[][];
  candidates: { model: string; label: string; mapped: number; unmapped: number }[]; model: string | null;
  mapping: Record<string, string | null>; questions: ImportQuestion[]; missing_required: string[];
  step: Partial<PlanStep> | null;
};
export type ImportPreview = { job: string; tables: ImportTable[]; notes: string[]; targets: { model: string; label: string }[] };

/* ---------------------------------------------------------------- stage 2: Change records */
export type ChangeTool = "transitions" | "edit" | "duplicates" | "activities" | "portal" | "security" | "message" | "recompute";
export type Batch = {
  id: string; name: string;
  payload: {
    tool: ChangeTool; model: string; domain: unknown[]; ids: number[]; change: Record<string, unknown>; hash: string;
    check: BatchCheck | null; approval?: Approval | null;
  };
};
export type RecordVerdict = "ready" | "no_change" | "blocked" | "over_cap";
export type BatchRecord = { id: number; name: string; verdict: RecordVerdict; reason?: string; fix?: string; now?: unknown; after?: unknown; user_id?: number; due?: string; group?: string };
export type BatchCheck = {
  hash: string; refused: string | null; records: BatchRecord[]; counts: Record<RecordVerdict, number>; over_cap?: number;
  limits: { cap: number; batch: number; pace_ms: number }; needs_approval?: boolean; threshold?: number; also?: string[]; receipt: string | null; checked_at?: string;
};
export type ChangeRunRecord = { id: number; name: string; state: "waiting" | "done" | "no_change" | "skipped" | "failed"; message?: string; after?: unknown };
export type ChangeRun = {
  id: string; name: string;
  payload: { batch_id: string; kind: "run" | "undo"; tool: ChangeTool; model: string; state: "scheduled" | "queued" | "running" | "stopped" | "cancelled" | "done" | "failed"; message?: string; fire_at?: string | null; repeat?: { every: string; until: string } | null; occurrence?: number;
    records: ChangeRunRecord[]; counts?: Record<string, number>; started_at: string; finished_at: string | null };
};
export type DuplicateGroup = { ids: number[]; strength: "Strong" | "Possible"; reasons: string[]; records: Record<string, unknown>[]; keep: number };
export type EditableField = { name: string; label: string; type: string; relation: string | null; choices: { value: string; label: string }[] };
const cb = (id: string) => `${base(id)}/change`;

export const changeApi = {
  buttons: (id: string) => request<{ record_types: { model: string; label: string; buttons: { key: string; label: string; money: boolean; effects: string[] }[] }[] }>(`${cb(id)}/buttons`),
  groups: (id: string) => request<{ groups: { id: number; name: string; xmlid: string | null; locked: boolean }[] }>(`${cb(id)}/groups`),
  computed: (id: string, model: string) => request<{ fields: { name: string; label: string }[] }>(`${cb(id)}/computed/${encodeURIComponent(model)}`),
  users: (id: string) => request<{ users: { id: number; name: string }[] }>(`${cb(id)}/users`),
  fields: (id: string, model: string) => request<{ fields: EditableField[] }>(`${cb(id)}/fields/${encodeURIComponent(model)}`),
  create: (id: string, body: { tool: ChangeTool; model: string; name?: string; domain?: unknown[]; ids?: number[]; change: Record<string, unknown> }) => post<Batch>(`${cb(id)}/batches`, body),
  update: (id: string, batchId: string, body: { tool: ChangeTool; model: string; name?: string; domain?: unknown[]; ids?: number[]; change: Record<string, unknown> }) => put<Batch>(`${cb(id)}/batches/${batchId}`, body),
  get: (id: string, batchId: string) => request<Batch>(`${cb(id)}/batches/${batchId}`),
  batches: (id: string) => request<{ batches: { id: string; name: string; tool: ChangeTool | null }[] }>(`${cb(id)}/batches`),
  scan: (id: string, model: string, domain: unknown[], fields: string[]) => post<{ groups: DuplicateGroup[] }>(`${cb(id)}/duplicates/scan`, { model, domain, fields }),
  check: (id: string, batchId: string) => post<BatchCheck>(`${cb(id)}/batches/${batchId}/dry-run`),
  requestApproval: (id: string, batchId: string) => post<{ item_id: string; status: string }>(`${cb(id)}/batches/${batchId}/request-approval`),
  run: (id: string, batchId: string) => post<ChangeRun>(`${cb(id)}/batches/${batchId}/run`),
  getRun: (id: string, runId: string) => request<ChangeRun>(`${cb(id)}/runs/${runId}`),
  stop: (id: string, runId: string) => post<{ ok: boolean }>(`${cb(id)}/runs/${runId}/stop`),
  reschedule: (id: string, runId: string, send_at: string, move: "this" | "series" = "this") => post<{ ok: boolean; fire_at: string }>(`${cb(id)}/runs/${runId}/reschedule`, { send_at, move }),
  cancel: (id: string, runId: string) => post<{ ok: boolean; state: string }>(`${cb(id)}/runs/${runId}/cancel`),
  runs: (id: string) => request<{ runs: { id: string; name: string; state: string; kind: string; tool: ChangeTool; batch_id: string; started_at: string; fire_at: string | null; repeat?: { every: string; until: string } | null }[] }>(`${cb(id)}/runs`),
  undo: (id: string, runId: string) => post<ChangeRun>(`${cb(id)}/runs/${runId}/undo`),
  exportCsv: async (id: string, runId: string): Promise<Blob> => {
    const res = await fetchApi(`${cb(id)}/runs/${runId}/export`);
    if (!res.ok) throw new Error(res.statusText);
    return res.blob();
  },
};

/* ---------------------------------------------------------------- stage 2: Upkeep, Safety, Ask */
export type Schedule = {
  id: number; name: string; record_type: string; how_often: string; description: string; description_source: string; active: boolean;
  next_run: string | null; last_result: string; failing: boolean; paused: { by: string; at: string; reason: string } | null; next_24h: string[];
};
export type FileRow = { id: number; name: string; size: number; checksum: string; created?: string };
export type FileScan = {
  files: number; stored_bytes: number; logical_bytes: number; breakdown: { model: string; files: number; bytes: number }[];
  accounting_excluded: number; unattached: FileRow[]; repeats: { checksum: string; size: number; keep: number; copies: number[]; all: number[] }[]; space_if_all_cleaned: number;
};
export type FileCheck = { verdicts: { id: number; name?: string; verdict: "ready" | "blocked"; reason?: string; why?: string; size?: number }[]; ready: number; blocked: number; space_freed: number; note: string };
export type UpgradeRow = { id: number; name: string; model: string; type: string; parent?: string; status: "ok" | "needs_fix"; flags: { key: string; text: string; fix: "auto" | "manual" }[]; fixed_arch: string | null };
export type UpgradeReport = { from_version: number; target_version: number; timeline: { what: string; value: string }[]; changes: UpgradeRow[]; needs_fix: number };
export type Localization = { companies: { name: string; country: string | null; currency: string | null }[]; country_packages: string[]; routes: Record<string, string>; rule: string };
export type AskPlan = { record_type: string; label: string; filters: unknown[][]; change: { tool: ChangeTool; button?: string; field?: string; value?: unknown } };
export type AskAnswer = { kind: "money"; route: string; answer: string } | { kind: "unclear"; unclear: string; dropped: string[]; source: string; timing?: AnswerTiming } | { kind: "plan"; plan: AskPlan; dropped: string[]; source: string; timing?: AnswerTiming };
/** Q2 touch 111: cached is true only for a real AI cache hit. */
export type AnswerTiming = { cached: boolean; seconds: number };
export type Guide = {
  question: string | null; decided: string | null; why_asking: string | null; source: string;
  options: { label: string; what_changes: string; affects_fact_ids: string[]; reversible: "easy" | "hard" | "after_posting_no" }[];
  facts: { id: string; label: string; value: unknown }[];
};

export type UpgradeForecast = {
  from_version: number; summary: string;
  steps: { version: number; screens_to_fix: number; auto_fixable: number; screens: { name: string; flags: string[] }[]; data_moves: string[] }[];
};
export type EveryVersionReport = {
  same_everywhere: boolean;
  results: { connection_id: string; version?: string; error?: string; can_apply?: boolean; counts?: CheckReport["counts"];
    problems?: { step: string; verdict: string; message: string }[] }[];
};

export const upkeepApi = {
  forecast: (id: string) => request<UpgradeForecast>(`${base(id)}/safety/upgrade/forecast`),
  schedules: (id: string) => request<{ schedules: Schedule[]; now: string }>(`${base(id)}/upkeep/schedules`),
  pause: (id: string, cronId: number, reason: string) => post<{ paused: Schedule["paused"] }>(`${base(id)}/upkeep/schedules/${cronId}/pause`, { reason }),
  resume: (id: string, cronId: number) => post<{ active: boolean }>(`${base(id)}/upkeep/schedules/${cronId}/resume`),
  files: (id: string) => request<FileScan>(`${base(id)}/upkeep/files`),
  checkFiles: (id: string, ids: number[]) => post<FileCheck>(`${base(id)}/upkeep/files/dry-run`, { ids }),
  cleanFiles: (id: string, ids: number[]) => post<{ run_id: string; removed: number; space_freed: number }>(`${base(id)}/upkeep/files/run`, { ids }),
  undoClean: (id: string, runId: string) => post<{ restored: number }>(`${base(id)}/upkeep/files/runs/${runId}/undo`),
  upgrade: (id: string, target?: string) => request<UpgradeReport>(`${base(id)}/safety/upgrade${target ? `?target=${encodeURIComponent(target)}` : ""}`),
  checkFix: (id: string, target: string, viewId: number) => post<{ ticket: { view: string; flags: UpgradeRow["flags"]; fixed_arch?: string }; passes: boolean; missing: string[]; note?: string }>(`${base(id)}/safety/upgrade/fix/dry-run`, { target, view_id: viewId }),
  localization: (id: string) => request<Localization>(`${base(id)}/safety/localization`),
  ask: (id: string, text: string) => post<AskAnswer>(`${base(id)}/ask`, { text }),
  /** Q2 touch 105: same as ask, but each real pipeline stage reports a step as it finishes. */
  askStream: async (id: string, text: string, onStep: (text: string) => void, signal?: AbortSignal): Promise<AskAnswer> => {
    const res = await fetchApi(`${base(id)}/ask/stream`, { method: "POST", body: JSON.stringify({ text }), signal });
    if (!res.ok || !res.body) throw new Error(formatDetailMessage((await res.json().catch(() => ({}))).detail) || `Ask failed (${res.status})`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      buf += dec.decode(value ?? new Uint8Array(), { stream: !done });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const ev = JSON.parse(line) as { type: string; text?: string; data?: AskAnswer; detail?: unknown };
        if (ev.type === "step" && ev.text) onStep(ev.text);
        else if (ev.type === "result" && ev.data) return ev.data;
        else if (ev.type === "error") throw new Error(formatDetailMessage(ev.detail) || "Ask failed");
      }
      if (done) throw new Error("Ask ended without an answer");
    }
  },
  ticket: (id: string, plan: AskPlan) => post<{ batch: Batch; next: string }>(`${base(id)}/ask/ticket`, { plan }),
  guideTopics: (id: string) => request<{ topics: { key: string; label: string }[] }>(`${base(id)}/ask/guide`),
  guide: (id: string, topic: string) => request<Guide>(`${base(id)}/ask/guide/${topic}`),
};

/* ---------------------------------------------------------------- stage 2 addition: record editor */
export type RecField = {
  name: string; label: string; type: string; relation: string | null; required: boolean; stored: boolean; editable: boolean; why_not: string | null;
  sortable: boolean; groupable: boolean; choices: { value: string; label: string }[];
};
export type RecMeta = { model: string; label: string; fields: RecField[]; columns: string[]; view_only: string | null; has_active: boolean };
export type RecRow = Record<string, unknown> & { id: number; display_name: string };
export type RecSearch = { total: number; offset: number; limit: number; rows: RecRow[]; groups: { value: unknown; label: string; count: number }[] | null };
export type RecEdit = { id: number; field: string; value: unknown };
const rb = (id: string) => `${base(id)}/records`;
export const recordsApi = {
  models: (id: string, q: string) => request<{ models: { model: string; label: string; view_only: string | null }[] }>(`${rb(id)}/models?q=${encodeURIComponent(q)}`),
  meta: (id: string, model: string) => request<RecMeta>(`${rb(id)}/${encodeURIComponent(model)}/meta`),
  search: (id: string, model: string, body: { search?: string; filters?: unknown[]; fields: string[]; group_by?: string | null; offset: number; limit: number; order?: string | null; archived?: boolean }) =>
    post<RecSearch>(`${rb(id)}/${encodeURIComponent(model)}/search`, body),
  replacePreview: (id: string, model: string, body: { field: string; find: string; replace: string; ids?: number[]; filters?: unknown[]; search?: string; whole?: boolean; case?: boolean }) =>
    post<{ edits: (RecEdit & { old: string; name: string })[]; count: number }>(`${rb(id)}/${encodeURIComponent(model)}/replace/preview`, body),
  plan: (id: string, model: string, edits: RecEdit[], name?: string) =>
    post<{ plan: Plan; steps: number; refused: (RecEdit & { problem: string })[] }>(`${rb(id)}/${encodeURIComponent(model)}/plan`, { edits, name: name ?? "" }),
};

export type InsightCard = { key: string; idea: number; title: string; what: string };
export const insightsApi = {
  list: (id: string) => request<{ insights: InsightCard[] }>(`${base(id)}/insights`),
  get: (id: string, key: string, q: Record<string, string> = {}) => {
    const qs = new URLSearchParams(q).toString();
    return request<Record<string, unknown>>(`${base(id)}/insights/${key}${qs ? `?${qs}` : ""}`);
  },
};
