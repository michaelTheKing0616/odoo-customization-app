import { request } from "./client";

export type CRModel = { model: string; name: string };
export type CRField = { type: string; string: string; relation?: string; selection?: [string, string][]; help?: string };
export type CRSchema = { major: number; models: CRModel[]; methods: Record<string, string>; deprecated: Record<string, { since: number; message: string; use: string }> };
export type CRIssue = { line: number; col: number; end_line: number; end_col: number; severity: "error" | "warning" | "info"; message: string; fix: string };
export type CRSnippet = { id: string; label: string; detail: string; body: string };
export type CRVersions = { model: string; labels: Record<string, string>; versions: string[]; missing_model: string[]; differing: number;
  rows: { field: string; differs: boolean; cells: Record<string, { type: string; string: string } | null> }[] };
export type CRAIAction = "explain" | "comment_to_code" | "fix";
export type CRAIOut = { ok: boolean; explanation: string; code: string; reason?: string; issues?: CRIssue[]; money?: string[] };

const base = (id: string) => `/api/connections/${id}/code-runner`;
const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

export const codeRunnerApi = {
  schema: (id: string) => request<CRSchema>(`${base(id)}/schema`),
  fields: (id: string, model: string) =>
    request<{ model: string; fields: Record<string, CRField> }>(`${base(id)}/schema/fields?model=${encodeURIComponent(model)}`),
  lint: (id: string, code: string, signal?: AbortSignal) => post<{ issues: CRIssue[] }>(`${base(id)}/lint`, { code }, signal),
  snippets: (id: string) => request<{ snippets: CRSnippet[] }>(`${base(id)}/snippets`),
  versions: (id: string, model: string, connection_ids: string[]) => post<CRVersions>(`${base(id)}/versions`, { model, connection_ids }),
  ai: (id: string, body: { action: CRAIAction; code: string; request?: string; error?: string }) => post<CRAIOut>(`${base(id)}/ai`, body),
};

// ---- R2: runs ---------------------------------------------------------------
export type CRChange = { op: "create" | "write" | "unlink" | "method"; model: string; id?: number; ids?: number[]; method?: string;
  label?: string; before: Record<string, unknown> | null; after: Record<string, unknown> | null; url?: string };
export type CREvent = { t: "log" | "error" | "progress"; msg?: string; group?: string; line?: number; message?: string; hint?: string; done?: number; total?: number };
export type CRSafety = { level: "none" | "low" | "medium" | "high"; score: number; reasons: string[]; money: string[]; needs_approval: boolean; undoable: boolean; calls: number };
export type CRProfile = { lines: { line: number; calls: number; ms: number; methods: string[]; source: string }[]; fixes: { line: number; fix: string }[]; total_ms: number; calls: number };
export type CRRunSummary = { id: string; mode: "dry" | "real"; status: string; created_at: number; ended_at: number | null; code_hash: string;
  safety: CRSafety | null; estimate: { records: number; sampled: number; seconds: number; writes: number; basis: string } | null;
  approval: { approved: boolean; by: string | null } | null; receipt_of: string | null; undo_of: string | null; resume_of: string | null;
  progress: { done: number; total: number } | null; counts: Record<string, number> | null; error: { line: number; message: string; hint: string; kind: string } | null; name: string };
export type CRRun = CRRunSummary & { events: CREvent[]; events_total: number; changes: CRChange[]; changes_total: number;
  results: Record<string, unknown>[]; profile: CRProfile | null; calls_total: number; timing_ms: number | null; code: string };

export const codeRunnerRunsApi = {
  start: (id: string, body: { code: string; mode?: "dry" | "real"; sample?: boolean; receipt_id?: string | null; name?: string }) =>
    post<CRRunSummary>(`${base(id)}/runs`, body),
  list: (id: string) => request<{ runs: CRRunSummary[] }>(`${base(id)}/runs`),
  get: (id: string, runId: string) => request<CRRun>(`${base(id)}/runs/${runId}`),
  control: (id: string, runId: string, action: "pause" | "resume" | "stop") => post<{ state: string }>(`${base(id)}/runs/${runId}/control`, { action }),
  approve: (id: string, runId: string) => post<{ approved: boolean }>(`${base(id)}/runs/${runId}/approve`, {}),
  resume: (id: string, runId: string) => post<CRRunSummary>(`${base(id)}/runs/${runId}/resume`, {}),
  undoPreview: (id: string, runId: string) => request<{ code: string; undoable: boolean }>(`${base(id)}/runs/${runId}/undo-preview`),
  undo: (id: string, runId: string) => post<CRRunSummary>(`${base(id)}/runs/${runId}/undo`, {}),
  exportUrl: (id: string, runId: string, fmt: "csv" | "json") => `${base(id)}/runs/${runId}/export?fmt=${fmt}`,
};

// ---- R3: library, gallery, notebooks, tests, promotions, audit, vault, settings ----------
export type CRScriptSummary = { id: string; name: string; folder: string; tags: string[]; kind: "script" | "notebook"; updated_at: number;
  updated_by: string | null; rev: number; shared_connections: string[] | null; versions: number; open_comments: number };
export type CRCell = { id: string; type: "code" | "markdown"; source: string };
export type CRComment = { id: string; line: number; text: string; by: string; at: number; resolved?: boolean; replies?: { text: string; by: string; at: number }[] };
export type CRParam = { name: string; label: string; type: "text" | "number" | "bool" | "date" | "id" | "ids" | "model" | string; default: unknown; required: boolean };
export type CRTest = { name: string; expect: Record<string, unknown> };
export type CRScript = CRScriptSummary & { code: string; cells: CRCell[]; comments: CRComment[]; tests: CRTest[]; params: CRParam[];
  version_list: { n: number; at: number; by: string | null; note: string }[] };
export type CRLive = { ok?: boolean; rev: number; code: string; cells: CRCell[]; editors?: { who: string; line: number | null }[] };
export type CRStarter = { id: string; title: string; category: string; risk: "reads" | "writes"; code: string; params: CRParam[] };
export type CRShareCheck = { connection_id: string; name?: string; major?: number; ok: boolean; errors: string[]; warnings?: string[] };
export type CRRunbookStep = { cell: string; run_id?: string; status: string; error?: unknown; message?: string; counts?: Record<string, number> | null };
export type CRTestResult = { name: string; where: string; passed: boolean; failures: string[]; run_id?: string };
export type CRPromotion = { id: string; name: string; kind: "cron" | "action" | "button"; model: string; status: string; by: string | null; at: number;
  interval: { number: number; type: string } | null; records: Record<string, number> };
export type CRAuditItem = { kind: string; at: number; by: string | null; run_id?: string; name?: string; status?: string; counts?: Record<string, number> | null;
  undo: string | null; undone_by?: string | null; [k: string]: unknown };
export type CRSecret = { name: string; set_by: string | null; set_at: number; connections: string[] };
export type CRSettings = { ai_mode: "local" | "cloud"; consent: { by: string; by_at: number } | null };

const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });
const q = (o: Record<string, string>) => new URLSearchParams(Object.entries(o).filter(([, v]) => v)).toString();

export const codeRunnerLibraryApi = {
  search: (id: string, f: { q?: string; folder?: string; tag?: string } = {}) =>
    request<{ scripts: CRScriptSummary[]; folders: string[]; tags?: string[] }>(`${base(id)}/library?${q({ q: f.q ?? "", folder: f.folder ?? "", tag: f.tag ?? "" })}`),
  create: (id: string, body: { name: string; code: string; folder?: string; tags?: string[]; kind?: "script" | "notebook"; cells?: CRCell[] }) =>
    post<CRScriptSummary & { code: string; cells: CRCell[] }>(`${base(id)}/library`, body),
  get: (id: string, sid: string) => request<CRScript>(`${base(id)}/library/${sid}`),
  meta: (id: string, sid: string, body: { name?: string; folder?: string; tags?: string[]; tests?: CRTest[] }) => patch<CRScriptSummary>(`${base(id)}/library/${sid}`, body),
  remove: (id: string, sid: string) => del<{ deleted: boolean }>(`${base(id)}/library/${sid}`),
  saveVersion: (id: string, sid: string, note: string) => post<{ n: number }>(`${base(id)}/library/${sid}/versions`, { note }),
  diff: (id: string, sid: string, a: number, b?: number) =>
    request<{ diff: string; left: string; right: string }>(`${base(id)}/library/${sid}/diff?a=${a}${b ? `&b=${b}` : ""}`),
  restore: (id: string, sid: string, n: number) => post<CRLive>(`${base(id)}/library/${sid}/restore/${n}`, {}),
  liveGet: (id: string, sid: string, line?: number) => request<CRLive>(`${base(id)}/library/${sid}/live${line ? `?line=${line}` : ""}`),
  livePut: (id: string, sid: string, body: { base_rev: number; code: string; cells?: CRCell[] }) => put<CRLive>(`${base(id)}/library/${sid}/live`, body),
  comment: (id: string, sid: string, line: number, text: string) => post<CRComment>(`${base(id)}/library/${sid}/comments`, { line, text }),
  resolveComment: (id: string, sid: string, cid: string, body: { reply?: string; resolved?: boolean }) =>
    patch<CRComment>(`${base(id)}/library/${sid}/comments/${cid}`, body),
  params: (id: string, code: string, values: Record<string, unknown> = {}) =>
    post<{ fields: CRParam[]; values: Record<string, unknown>; errors: string[] }>(`${base(id)}/params`, { code, values }),
  share: (id: string, sid: string, connection_ids: string[]) => post<{ checks: CRShareCheck[]; shared: string[] }>(`${base(id)}/library/${sid}/share`, { connection_ids }),
  gallery: (id: string) => request<{ starters: CRStarter[] }>(`${base(id)}/gallery`),
  runbook: (id: string, sid: string, body: { mode: "dry" | "real"; receipts?: Record<string, string>; params?: Record<string, unknown> }) =>
    post<{ steps: CRRunbookStep[]; complete: boolean }>(`${base(id)}/library/${sid}/runbook`, body),
  runTests: (id: string, sid: string) => post<{ results: CRTestResult[]; passed: boolean }>(`${base(id)}/library/${sid}/tests/run`, {}),
};

export const codeRunnerOpsApi = {
  promoteCheck: (id: string, code: string) => post<{ ok: boolean; reasons: string[] }>(`${base(id)}/promotions/check`, { code }),
  promotions: (id: string) => request<{ promotions: CRPromotion[] }>(`${base(id)}/promotions`),
  promote: (id: string, body: { script_id?: string | null; name: string; code: string; params?: Record<string, unknown>; kind: "cron" | "action" | "button";
    model?: string; interval?: { number: number; type: string } | null; receipt_id: string }) => post<CRPromotion>(`${base(id)}/promotions`, body),
  promotionAction: (id: string, pid: string, action: "run-once" | "publish" | "remove") => post<CRPromotion>(`${base(id)}/promotions/${pid}/${action}`, {}),
  audit: (id: string) => request<{ items: CRAuditItem[] }>(`${base(id)}/audit`),
  vault: (id: string) => request<{ secrets: CRSecret[] }>(`${base(id)}/vault`),
  setSecret: (id: string, body: { name: string; value: string; connections: string[] }) => post<{ ok: boolean }>(`${base(id)}/vault`, body),
  deleteSecret: (id: string, name: string) => del<{ deleted: boolean }>(`${base(id)}/vault/${encodeURIComponent(name)}`),
  settings: (id: string) => request<CRSettings>(`${base(id)}/settings`),
  saveSettings: (id: string, body: { mode: "local" | "cloud"; consent: boolean }) => put<CRSettings>(`${base(id)}/settings`, body),
};
