import { request } from "./client";

/** One node of a normalized Odoo screen (same shape on Odoo 17, 18, 19 and 20). */
export type EngineNode = {
  id: string;
  tag: string;
  kind: string;
  name: string | null;
  label: string;
  attrs: Record<string, string>;
  anchor: string | null;
  locked_reason: string | null;
  children: EngineNode[];
  field_type?: string | null;
  relation?: string | null;
  has_subview?: boolean;
  known_field?: boolean;
  /** Plain "why" sentence per rule attribute (invisible, required, readonly, column_invisible). */
  rules?: Partial<Record<RuleAttr, string>>;
  /** Set when the safe address relies on the item's settings, which may change on upgrade. */
  anchor_note?: string;
  /** Hidden helper Odoo adds for values other parts of the screen need. */
  helper?: boolean;
};

export type RuleAttr = "invisible" | "required" | "readonly" | "column_invisible";
export type ConditionRule = { field: string; op: string; value?: unknown };
export type Condition = { match: "all" | "any"; rules: ConditionRule[] };

export type EngineField = {
  string?: string;
  type?: string;
  required?: boolean;
  readonly?: boolean;
  relation?: string;
  store?: boolean;
};

export type EngineViewType = "form" | "list" | "kanban" | "search" | "calendar";

export type EngineOp =
  | { op: "move"; node: string; target: string; position: "before" | "after" | "inside" }
  | { op: "hide"; node: string }
  | { op: "set_attr"; node: string; attr: string; value: string; force?: boolean }
  | { op: "wrap"; nodes: string[]; kind: "group" | "page" | "notebook"; label: string }
  | { op: "set_condition"; node: string; attr: RuleAttr; sense: "show" | "hide"; condition: Condition | null; keep_existing?: boolean; copy_from?: string }
  | { op: "set_access"; node: string; edit: string[]; see: string[] }
  | { op: "insert_field"; field: string; target: string; position: "before" | "after" | "inside"; widget?: string; string?: string; placeholder?: string; optional?: "show" | "hide" }
  | { op: "insert_element"; element: string; target: string; position: "before" | "after" | "inside"; props?: Record<string, unknown> }
  | { op: "set_decoration"; node: string; style: string; condition: Condition | null }
  | { op: "kanban_add"; kind: string; field?: string; props?: Record<string, unknown>; condition?: Condition | null }
  | { op: "search_add_filter"; label: string; condition: Condition }
  | { op: "search_add_groupby"; field: string; label?: string }
  | { op: "search_add_field"; field: string; label?: string }
  | { op: "insert_section"; xml: string; target: string; position: "before" | "after" | "inside"; skip?: string[] };

export type EngineLayer = { id: number; active: boolean; steps: number; arch?: string } | null;

export type EngineLoadOut = {
  major: number;
  model: string;
  view_type: EngineViewType;
  base_view_id: number;
  combined_arch: string;
  arch_hash: string;
  tree: EngineNode;
  fields: Record<string, EngineField>;
  layer: EngineLayer;
  /** Layer as loaded; sent back on publish so someone else's publish is never overwritten. */
  layer_hash?: string;
};

export type EngineRecord = { id: number; display_name: string } & Record<string, unknown>;

export type EngineRecordsOut = {
  records: EngineRecord[];
  total: number;
  fields: string[];
  picks: { longest: number | null; emptiest: number | null };
};

export type EngineCompileOut = {
  arch: string;
  steps: Array<{ op: string; xpath: string[] }>;
  dropped: string[];
  warnings: string[];
  issues: Array<{ severity: string; code: string; message: string }>;
  blocking: boolean;
  expected_tree: EngineNode;
};

export type EnginePublishOut = {
  role_layouts?: string[];
  ok: boolean;
  layer_view_id: number;
  previous_arch: string | null;
  layer_arch: string;
  steps: number;
  dropped: string[];
  warnings: string[];
  fidelity: { ok: boolean; differences: string[] };
  stock_unchanged: boolean;
  arch_hash_before: string;
  arch_hash_after: string;
  version_id?: string | null;
  layer_hash?: string;
};

export type ReportBlock =
  | { type: "text"; text: string }
  | { type: "heading"; text: string; level?: number }
  | { type: "field"; field: string }
  | { type: "label_field"; field: string; label?: string }
  | { type: "divider" };

export type ReportSlot = { id: string; label: string; xpath: string; position: string };

export type ReportLoadOut = {
  major: number;
  model: string;
  reports: Array<{ id: number; name: string; report_name: string }>;
  report: { id: number; name: string; report_name: string; model: string } | null;
  document?: { key: string; view_id: number };
  slots?: ReportSlot[];
  record_var?: string;
  fields?: Record<string, EngineField>;
  records: Array<{ id: number; display_name: string }>;
  layer?: { id: number; active: boolean } | null;
};

export type ReportPublishOut = {
  ok: boolean;
  layer_view_id: number;
  previous_arch: string | null;
  layer_arch: string;
  pages: number;
  stock_unchanged: boolean;
  content_base64: string;
};

// ---- Stage 2a -------------------------------------------------------------

export type ConditionReading = {
  sense: "show" | "hide";
  condition: Condition;
  sentence: string;
  rule_sentence: string;
  expression: string;
};
export type ConditionValuesOut = { type: string; ops: Array<{ op: string; label: string }>; values?: Array<{ value: string | number; label: string }> };
export type ConditionCheckOut = { condition: Condition; sentence: string; expression: string; rule_sentence: string };
export type Role = { xmlid: string; id: number; name: string; people: number };
export type Person = { id: number; name: string; login: string };
export type Visibility = Record<string, { visible: boolean; reason: string | null; note?: string }>;
export type Perms = { read: boolean; write: boolean; create: boolean; unlink: boolean };
export type PreviewAsOut = {
  who: { kind: "role" | "person"; name: string; xmlid?: string; id?: number };
  visibility: Visibility;
  also_sees: Array<{ name: string; label: string }>;
  perms: Perms;
  summary: string;
  read_only: boolean;
  based_on: string;
};
export type FieldImpactOut = {
  impact: string[];
  blocks: string[];
  warnings: string[];
  lose: Array<{ id: number; name: string }>;
  gain: Array<{ id: number; name: string }>;
  op: EngineOp;
  same_field_nodes?: string[];
  /** Odoo 17 refuses to limit this field to roles: offer a show/hide rule instead. */
  alternative?: { kind: "rule"; node: string; nodes: string[]; attr: "invisible"; sense: "hide"; label: string } | null;
};
export type AccessRow = Perms & { id: number; name: string; group: string | null; group_name: string; ingenium: boolean; domain?: string };
export type ModelAccessOut = {
  model: string;
  label: string;
  rows: AccessRow[];
  roles: Array<{ group: string; name: string; perms: Perms; people: number }>;
  everyone: Perms | null;
  rules: Array<{ id: number; name: string; applies_to: string; domain: string; plain: string | null; perms: string[]; kind?: string }>;
  editable: boolean;
  rules_link: string;
};
export type AccessChange = { group: string } & Partial<Perms>;
export type AccessUndo = Array<{ type: string; id: number; perms?: Partial<Perms> }>;
export type VersionRow = { version: number; current: boolean; available: boolean; flags: string[]; tree: EngineNode | null; source: string };
export type HistoryVersion = {
  id: string;
  action: string;
  label: string | null;
  summary: string[];
  layer_active: boolean;
  has_layer: boolean;
  created_at: string | null;
  odoo_major: number | null;
  layer_view_id: number | null;
};
export type Marker = "added" | "removed" | "moved" | "hidden" | "shown" | "changed";
export type CompareOut = { from_tree: EngineNode; to_tree: EngineNode; markers: Record<string, Marker>; changes: string[] };
export type ViewComment = {
  id: string;
  node_id: string;
  parent_id: string | null;
  author: string;
  body: string;
  resolved: boolean;
  created_at: string | null;
  resolved_at: string | null;
};
export type CommandOut = {
  ops: EngineOp[];
  unclear: string | null;
  descriptions: string[];
  op_descriptions?: string[];
  choices?: string[];
  markers: Record<string, Marker>;
  expected_tree?: EngineNode;
};
export type ReportDraftOut = { ok: boolean; pages: number; missing: string[]; content_base64: string };

type Screen = { model: string; view_type: EngineViewType; ops?: EngineOp[] };

const post = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

const eng = (id: string, path: string) => `/api/connections/${id}/views/engine/${path}`;

export const viewEngineApi = {
  engineLoad: (id: string, model: string, view_type: EngineViewType, view_id?: number | null) =>
    post<EngineLoadOut>(`/api/connections/${id}/views/engine/load`, { model, view_type, view_id: view_id ?? null }),
  engineRecords: (id: string, model: string, view_type: EngineViewType, view_id?: number | null) =>
    post<EngineRecordsOut>(`/api/connections/${id}/views/engine/records`, { model, view_type, view_id: view_id ?? null, limit: 80 }),
  engineCompile: (id: string, model: string, view_type: EngineViewType, ops: EngineOp[], view_id?: number | null) =>
    post<EngineCompileOut>(`/api/connections/${id}/views/engine/compile`, { model, view_type, ops, view_id: view_id ?? null }),
  enginePublish: (
    id: string,
    model: string,
    view_type: EngineViewType,
    ops: EngineOp[],
    summary?: string[],
    extra?: { view_id?: number | null; base_layer_hash?: string | null },
  ) =>
    post<EnginePublishOut & { version_id?: string | null; layer_hash?: string; cleaned_access?: boolean }>(
      `/api/connections/${id}/views/engine/publish`,
      { model, view_type, ops, summary, view_id: extra?.view_id ?? null, base_layer_hash: extra?.base_layer_hash ?? null },
    ),
  engineRevert: (
    id: string,
    body: {
      model: string;
      view_type: EngineViewType;
      layer_view_id: number;
      mode: "deactivate" | "restore" | "remove";
      restore_arch?: string | null;
      view_id?: number | null;
    },
  ) => post<{ ok: boolean; arch_hash_after: string }>(`/api/connections/${id}/views/engine/revert`, body),
  reportEngineLoad: (id: string, model: string, report_id?: number | null) =>
    post<ReportLoadOut>(`/api/connections/${id}/reports/engine/load`, { model, report_id: report_id ?? null }),
  reportEngineProof: (id: string, body: { report_id: number; record_id: number }) =>
    post<{ ok: boolean; pages: number; content_base64: string }>(`/api/connections/${id}/reports/engine/proof`, {
      ...body,
      blocks: [],
    }),
  reportEnginePublish: (id: string, body: { report_id: number; record_id: number; slot: string; blocks: ReportBlock[] }) =>
    post<ReportPublishOut>(`/api/connections/${id}/reports/engine/publish`, body),
  reportEngineRevert: (id: string, body: { layer_view_id: number; mode: "deactivate" | "remove" }) =>
    post<{ ok: boolean }>(`/api/connections/${id}/reports/engine/revert`, body),
  reportEngineDraft: (
    id: string,
    body: { report_id: number; record_id: number; slot: string; blocks: ReportBlock[] },
    signal?: AbortSignal,
  ) => post<ReportDraftOut>(`/api/connections/${id}/reports/engine/draft`, body, signal),

  // Show and hide rules
  conditionValues: (id: string, model: string, field: string, query = "") =>
    post<ConditionValuesOut>(eng(id, "conditions/values"), { model, field, query }),
  conditionCheck: (id: string, model: string, attr: RuleAttr, sense: "show" | "hide", condition: Condition) =>
    post<ConditionCheckOut>(eng(id, "conditions/check"), { model, attr, sense, condition }),
  conditionWords: (id: string, model: string, attr: RuleAttr, text: string) =>
    post<{ readings: ConditionReading[]; unclear: string | null }>(eng(id, "conditions/words"), { model, attr, text }),

  // Who can see it
  roles: (id: string) => post<{ roles: Role[]; admin_role: string; based_on: string }>(eng(id, "roles"), {}),
  people: (id: string, query: string) => post<{ people: Person[] }>(eng(id, "people"), { query }),
  previewAs: (id: string, screen: Screen, who: { role?: string; user_id?: number }) =>
    post<PreviewAsOut>(eng(id, "preview-as"), { ...screen, ...who }),
  fieldImpact: (id: string, screen: Screen, body: { node: string; edit: string[]; see: string[]; also?: string[] }) =>
    post<FieldImpactOut>(eng(id, "access/field-impact"), { ...screen, ...body }),
  modelAccess: (id: string, model: string) => post<ModelAccessOut>(eng(id, "access/model"), { model }),
  modelAccessPreview: (id: string, model: string, changes: AccessChange[]) =>
    post<{ impact: string[]; blocks: string[]; actions: number }>(eng(id, "access/model/preview"), { model, changes }),
  modelAccessApply: (id: string, model: string, changes: AccessChange[]) =>
    post<{ ok: boolean; impact: string[]; undo: AccessUndo }>(eng(id, "access/model/apply"), { model, changes }),
  modelAccessUndo: (id: string, model: string, undo: AccessUndo) =>
    post<{ ok: boolean }>(eng(id, "access/model/undo"), { model, undo }),

  // Versions side by side
  versions: (id: string, screen: Screen) => post<{ current: number; versions: VersionRow[] }>(eng(id, "versions"), screen),

  // History
  historyList: (id: string, model: string, view_type: EngineViewType) =>
    post<{ versions: HistoryVersion[] }>(eng(id, "history/list"), { model, view_type }),
  historyName: (id: string, version_id: string, label: string) => post<HistoryVersion>(eng(id, "history/name"), { version_id, label }),
  historyTree: (id: string, version_id: string) =>
    post<{ version: HistoryVersion; tree: EngineNode }>(eng(id, "history/tree"), { version_id }),
  historyCompare: (id: string, model: string, view_type: EngineViewType, from_id: string, to_id = "current") =>
    post<CompareOut>(eng(id, "history/compare"), { model, view_type, from_id, to_id }),
  historyRestore: (id: string, version_id: string) =>
    post<{ ok: boolean; version_id: string; layer_view_id: number; previous_arch: string | null; previous_active: boolean }>(
      eng(id, "history/restore"),
      { version_id },
    ),

  // Comments pinned to items
  commentsList: (id: string, model: string, view_type: EngineViewType) =>
    post<{ comments: ViewComment[] }>(eng(id, "comments/list"), { model, view_type }),
  commentsAdd: (id: string, body: { model: string; view_type: EngineViewType; node_id: string; body: string; parent_id?: string | null }) =>
    post<ViewComment>(eng(id, "comments/add"), body),
  commentsResolve: (id: string, commentId: string, resolved: boolean) =>
    post<ViewComment>(eng(id, "comments/resolve"), { id: commentId, resolved }),
  commentsDelete: (id: string, commentId: string) => post<{ ok: boolean }>(eng(id, "comments/delete"), { id: commentId }),

  // Command bar (AI proposes, the server checks)
  command: (id: string, screen: Screen, text: string) => post<CommandOut>(eng(id, "command"), { ...screen, text }),
};
