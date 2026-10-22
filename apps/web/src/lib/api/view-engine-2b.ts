import { request } from "./client";
import type { Condition, EngineOp, EngineViewType } from "./view-engine";

// ---- View designer, stage 2b ------------------------------------------------

export type Screen2b = { model: string; view_type: EngineViewType; view_id?: number | null; ops?: EngineOp[] };
export type Widget = { name: string; label: string };
export type FieldType = { key: string; label: string; ttype?: string; needs?: string; widget?: string };
export type LibraryItem = { kind: string; label: string; props?: Record<string, unknown> };
export type ExistingField = { name: string; label: string; type: string; on_screen: boolean; widgets: Widget[] };
export type LibraryOut = {
  major: number;
  root_tag: string;
  field_types: FieldType[];
  layout: LibraryItem[];
  buttons: LibraryItem[];
  existing_fields: ExistingField[];
};
/** One finding with an optional one-click fix (ops for the normal compile/publish path). */
export type Finding = {
  kind: string;
  node?: string;
  text: string;
  detail?: string;
  severity?: string;
  fix_label?: string | null;
  ops: EngineOp[];
  rate?: number;
};
export type Health = { score: number; parts: Array<{ key: string; label: string; score: number }>; summary?: string };
export type ChecksOut = { health: Health; issues: Finding[]; suggestions: Finding[]; performance: Finding[]; total: number };
export type TidyOut = { ops: EngineOp[]; descriptions: string[]; note: string | null; sections: Record<string, string> };
export type FieldSpec = {
  type: string;
  label: string;
  relation?: string;
  relation_field?: string;
  related?: string;
  choices?: Array<[string, string]> | string[];
  required?: boolean;
  help?: string;
};
export type FieldCreateOut =
  | { created: true; id: number; name: string; widget: string | null; label: string; type: string }
  | { created: false; similar: Array<{ name: string; label: string; type: string }>; message: string };
export type RelatedChoice = { field: string; label: string; relation: string; items: Array<{ path: string; label: string; type: string }> };
export type SmartOption = { relation: string; relation_label: string | null; field: string; field_label: string | null };

export type ScreenTemplate = { view_type: EngineViewType; key: string; label: string; available: boolean; reason: string | null };
export type BuilderItem<P = Record<string, unknown>> = { id: string; kind: string; key: string; name: string; payload: P; created_at: string | null };
export type ScreenItem = BuilderItem<{ view_id: number; action_id: number | null; menu_id: number | null; view_type: EngineViewType; template: string }> & {
  exists: boolean;
};
export type TranslationsOut = {
  languages: Array<{ code: string; name: string }>;
  rows: Array<{ node: string; en: string; langs: Record<string, string> }>;
  hint: string | null;
};
export type GuardStep = { index: number; status: "ok" | "overridden" | "missing"; text: string; reason: string };
export type GuardOut = {
  has_layer: boolean;
  screen_ok: boolean;
  problem: string | null;
  odoo_changed?: boolean;
  baseline_at?: string | null;
  baseline_major?: number | null;
  major?: number;
  steps?: GuardStep[];
  problems?: number;
  ok?: boolean;
  summary?: string;
};
export type SectionItem = BuilderItem<{ xml: string; fields: Array<{ name: string; type: string | null; label: string }>; tag: string; model: string }> & {
  fit?: { missing: Array<{ name: string; label: string }>; wrong_type: Array<{ name: string; label: string }>; fits: boolean };
};
export type LayoutPackage = Record<string, unknown> & { format: string; model: string; view_type: string; checksum: string };
export type PackageCheckOut = {
  ok: boolean;
  model: string;
  view_type: EngineViewType;
  base_view_id: number | null;
  fields_to_create: Array<{ name: string; ttype: string; field_description?: string }>;
  problems: string[];
  has_changes_here: boolean;
  steps: number;
  from_major: number;
  to_major: number;
};

// ---- Reports and emails, stage 2b ------------------------------------------------

export type ReportBlock2b =
  | { type: "text"; text: string; condition?: Condition | null }
  | { type: "heading"; text: string; level?: number; condition?: Condition | null }
  | { type: "field"; field: string; condition?: Condition | null }
  | { type: "label_field"; field: string; label?: string; condition?: Condition | null }
  | { type: "divider"; condition?: Condition | null }
  | { type: "spacer"; size?: "small" | "medium" | "large"; condition?: Condition | null }
  | {
      type: "line_table";
      field: string;
      columns: Array<{ field: string; label?: string; sum?: boolean; align?: "left" | "center" | "right" }>;
      totals_label?: string;
      condition?: Condition | null;
    }
  | { type: "qr" | "barcode"; field: string; condition?: Condition | null }
  | { type: "signature"; field: string; label?: string; signed_by?: string; condition?: Condition | null }
  | { type: "image_field"; field: string; condition?: Condition | null }
  | { type: "watermark"; text: string; colour?: "red" | "grey" | "blue" | "green"; condition?: Condition | null }
  | { type: "page_break"; condition?: Condition | null };
export type BlockType = ReportBlock2b["type"];
export type Placement = { slot: string; blocks: ReportBlock2b[] };
export type Slot2b = { id: string; label: string; xpath: string; position: string };
export type PageCheck = { kind: "overflow" | "image" | "split" | "pages"; level: "warning" | "info"; page: number | null; text: string };
export type LayoutLoadOut = {
  major: number;
  report: { id: number; name: string; report_name: string; model: string };
  document: { key: string; view_id: number };
  record_var: string;
  slots: Slot2b[];
  placements: Placement[] | null;
  earlier_changes: boolean;
  line_fields: string[];
  layer: { id: number; active: boolean } | null;
  blocks: BlockType[];
};
export type LineColumn = { name: string; label: string; type: string; can_total: boolean };
export type DraftOut2b = { ok: boolean; pages: number; missing: string[]; checks: PageCheck[]; content_base64: string };
export type CompareOut2b = {
  before_base64: string;
  after_base64: string;
  diff: { pages_before: number; pages_after: number; same: boolean; pages: Array<{ page: number; added: string[]; removed: string[] }> };
  checks: PageCheck[];
};
export type VisualPage = {
  page: number;
  width: number;
  height: number;
  before_png: string;
  after_png: string;
  overlay_png: string;
  changed_percent: number;
  only_in: "draft" | "published" | null;
  box?: { left: number; top: number; right: number; bottom: number };
  summary: string;
};
export type VisualCompareOut = {
  visual: { pages: VisualPage[]; same: boolean; page_counts: { published: number; draft: number }; truncated: boolean };
  diff: CompareOut2b["diff"];
};
export type LayoutPublishOut = {
  ok: boolean;
  layer_view_id: number;
  previous_arch: string | null;
  previous_placements: Placement[] | null;
  layer_arch: string;
  pages: number;
  checks: PageCheck[];
  content_base64: string;
};
export type VariantsOut = {
  languages: Array<{ code: string; name: string; record_id: number | null; note: string | null }>;
  currencies: Array<{ id: number; name: string; record_id: number }>;
  companies: Array<{ id: number; name: string; record_id: number }>;
};
export type BrandValues = Partial<{
  external_report_layout_id: number;
  primary_color: string;
  secondary_color: string;
  font: string;
  report_header: string;
  report_footer: string;
  layout_background: string;
}>;
export type BrandOptions = {
  company: Record<string, unknown> & { id: number; name: string };
  layouts: Array<{ name: string; view_id: number | null }>;
  fonts: string[];
  backgrounds: string[];
};
export type Starter = { key: string; label: string; placements: Placement[] };
export type BlockSet = BuilderItem<{ blocks: ReportBlock2b[] }> & { usable_in_email: boolean };
export type EmailTemplateRow = { id: number; name: string; subject: string | null; ingenium_copy: boolean; copied_from: number | null };
export type EmailLoadOut = {
  template: { id: number; name: string; subject: string | null; model: string };
  editable: boolean;
  placements: Placement[];
  slots: Slot2b[];
  blocks: BlockType[];
  line_fields: string[];
  fields: Record<string, { string?: string | null; type?: string | null }>;
  records: Array<{ id: number; display_name: string }>;
};
export type EmailPreviewOut = { subject: string; html: string; widths: { desktop: number; phone: number } };

const post = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });
const eng = (id: string, path: string) => `/api/connections/${id}/views/engine/${path}`;
const rep = (id: string, path: string) => `/api/connections/${id}/reports/engine/${path}`;
const mail = (id: string, path: string) => `/api/connections/${id}/emails/engine/${path}`;

export const viewEngine2bApi = {
  // Library, widgets, checks
  library: (id: string, screen: Screen2b) => post<LibraryOut>(eng(id, "library"), screen),
  widgets: (id: string, field_type: string) => post<{ major: number; widgets: Widget[] }>(eng(id, "widgets"), { field_type }),
  checks: (id: string, screen: Screen2b) => post<ChecksOut>(eng(id, "checks"), screen),
  tidy: (id: string, screen: Screen2b, use_ai = true) => post<TidyOut>(eng(id, "tidy"), { ...screen, use_ai }),
  presence: (id: string, screen: Screen2b, editor_id: string, name: string, leaving = false) =>
    post<{ others: Array<{ editor_id: string; name: string; seen_seconds_ago: number }>; ttl: number }>(eng(id, "presence"), {
      model: screen.model,
      view_type: screen.view_type,
      view_id: screen.view_id ?? null,
      editor_id,
      name,
      leaving,
    }),

  // Fields, defaults, smart buttons
  fieldCreate: (id: string, model: string, spec: FieldSpec, force = false) => post<FieldCreateOut>(eng(id, "fields/create"), { model, spec, force }),
  fieldDelete: (id: string, model: string, name: string) => post<{ ok: boolean }>(eng(id, "fields/delete"), { model, name }),
  inverseOptions: (id: string, model: string, relation: string) =>
    post<{ options: Array<{ name: string; label: string }> }>(eng(id, "fields/inverse-options"), { model, relation }),
  relatedChoices: (id: string, model: string) => post<{ choices: RelatedChoice[] }>(eng(id, "fields/related"), { model }),
  defaultGet: (id: string, model: string, field: string) => post<{ value: unknown; set: boolean }>(eng(id, "defaults/get"), { model, field }),
  defaultSet: (id: string, model: string, field: string, value: unknown, clear = false) =>
    post<{ ok: boolean; previous: unknown; had_previous: boolean }>(eng(id, "defaults/set"), { model, field, value, clear }),
  smartOptions: (id: string, model: string) => post<{ options: SmartOption[] }>(eng(id, "smart-button/options"), { model }),
  smartAction: (id: string, body: { model: string; relation: string; field: string; label: string; with_count: boolean }) =>
    post<{ ok: boolean; action_id: number; count_field?: string; count_field_id?: number }>(eng(id, "smart-button/action"), body),
  smartUndo: (id: string, body: { action_id?: number | null; count_field_id?: number | null }) => post<{ ok: boolean }>(eng(id, "smart-button/undo"), body),

  // New screens
  screenTemplates: (id: string, model: string) => post<{ templates: ScreenTemplate[]; screens: ScreenItem[] }>(eng(id, "screens/templates"), { model }),
  screenCreate: (id: string, body: { model: string; view_type: EngineViewType; template: string; label: string; make_menu: boolean; parent_menu_id?: number | null }) =>
    post<{ ok: boolean; item_id: string; view_id: number; action_id: number | null; menu_id: number | null; view_type: EngineViewType }>(
      eng(id, "screens/create"),
      body,
    ),
  screenDelete: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "screens/delete"), { item_id }),

  // Translations
  translations: (id: string, screen: Screen2b) => post<TranslationsOut>(eng(id, "translations/list"), screen),
  translationSave: (id: string, screen: Screen2b, node: string, translations: Record<string, string>, base_layer_hash?: string | null) =>
    post<{ ok: boolean; term: string; saved: Record<string, string>; previous: Record<string, string> }>(eng(id, "translations/save"), {
      ...screen,
      node,
      translations,
      base_layer_hash: base_layer_hash ?? null,
    }),

  // Upgrade guard
  guardCheck: (id: string, screen: Screen2b) => post<GuardOut>(eng(id, "guard/check"), screen),
  guardFix: (id: string, screen: Screen2b) =>
    post<{ ok: boolean; changed: boolean; dropped: string[]; priority: number | null; still_wrong?: GuardStep[]; message?: string }>(eng(id, "guard/fix"), screen),

  // Reusable sections
  sectionSave: (id: string, screen: Screen2b, node: string, name: string) => post<{ ok: boolean; section: SectionItem }>(eng(id, "sections/save"), { ...screen, node, name }),
  sectionList: (id: string, model: string) => post<{ sections: SectionItem[] }>(eng(id, "sections/list"), { model }),
  sectionDelete: (id: string, item_id: string) => post<{ ok: boolean }>(eng(id, "sections/delete"), { item_id }),

  // Package
  packageExport: (id: string, screen: Screen2b) => post<{ package: LayoutPackage; file_name: string }>(eng(id, "package/export"), screen),
  packageCheck: (id: string, pkg: LayoutPackage) => post<PackageCheckOut>(eng(id, "package/check"), { package: pkg }),
  packageImport: (id: string, pkg: LayoutPackage, replace = false) =>
    post<{ ok: boolean; fields_created: string[]; layer_view_id: number; base_view_id: number }>(eng(id, "package/import"), { package: pkg, replace }),

  // Reports
  layoutLoad: (id: string, report_id: number) => post<LayoutLoadOut>(rep(id, "layout/load"), { report_id }),
  linesFields: (id: string, report_id: number, field: string) => post<{ field: string; columns: LineColumn[] }>(rep(id, "lines-fields"), { report_id, field }),
  layoutDraft: (
    id: string,
    body: { report_id: number; record_id: number; placements: Placement[]; lang?: string | null; company_id?: number | null; published_pages?: number | null },
    signal?: AbortSignal,
  ) => post<DraftOut2b>(rep(id, "layout/draft"), body, signal),
  layoutCompare: (id: string, body: { report_id: number; record_id: number; placements: Placement[] }) => post<CompareOut2b>(rep(id, "layout/compare"), body),
  layoutCompareVisual: (id: string, body: { report_id: number; record_id: number; placements: Placement[] }) => post<VisualCompareOut>(rep(id, "layout/compare-visual"), body),
  layoutPublish: (id: string, body: { report_id: number; record_id: number; placements: Placement[] }) => post<LayoutPublishOut>(rep(id, "layout/publish"), body),
  variants: (id: string, report_id: number) => post<VariantsOut>(rep(id, "variants"), { report_id }),
  pageNumbersCheck: (id: string, company_id?: number | null) =>
    post<{ layout: string; stock_shows_numbers: boolean; ingenium_added: boolean; message: string }>(rep(id, "page-numbers/check"), { company_id: company_id ?? null }),
  pageNumbersSet: (id: string, on: boolean, company_id?: number | null) =>
    post<{ ok: boolean; on: boolean; note?: string }>(rep(id, "page-numbers/set"), { on, company_id: company_id ?? null }),
  brandOptions: (id: string, company_id?: number | null) => post<BrandOptions>(rep(id, "brand/options"), { company_id: company_id ?? null }),
  brandPreview: (id: string, values: BrandValues, company_id?: number | null) => post<{ html: string }>(rep(id, "brand/preview"), { values, company_id: company_id ?? null }),
  brandApply: (id: string, values: BrandValues, company_id?: number | null) =>
    post<{ ok: boolean; previous: BrandValues; applied: BrandValues }>(rep(id, "brand/apply"), { values, company_id: company_id ?? null }),
  brandUndo: (id: string, previous: BrandValues, company_id?: number | null) => post<{ ok: boolean }>(rep(id, "brand/undo"), { previous, company_id: company_id ?? null }),
  gallery: (id: string, report_id: number) => post<{ starters: Starter[]; major: number }>(rep(id, "gallery"), { report_id }),
  blockSetSave: (id: string, model: string, name: string, blocks: ReportBlock2b[]) =>
    post<{ ok: boolean; item: BlockSet; usable_in_email: boolean }>(rep(id, "blocks/save"), { model, name, blocks }),
  blockSetList: (id: string, model: string) => post<{ sets: BlockSet[] }>(rep(id, "blocks/list"), { model }),
  blockSetDelete: (id: string, item_id: string) => post<{ ok: boolean }>(rep(id, "blocks/delete"), { item_id }),

  aiEdit: (id: string, body: { report_id: number; text: string; placements: Placement[] }) => post<AIEditOut>(rep(id, "ai-edit"), body),
  aiApply: (id: string, body: { report_id: number; placements: Placement[]; ops: AIBlockOp[] }) => post<{ placements: Placement[] }>(rep(id, "ai-edit/apply"), body),
  emailAiEdit: (id: string, body: { template_id: number; text: string; placements: Placement[] }) => post<AIEditOut>(mail(id, "ai-edit"), body),
  emailAiApply: (id: string, body: { template_id: number; placements: Placement[]; ops: AIBlockOp[] }) => post<{ placements: Placement[] }>(mail(id, "ai-edit/apply"), body),

  // Emails
  emailList: (id: string, model: string) => post<{ templates: EmailTemplateRow[] }>(mail(id, "list"), { model }),
  emailCopy: (id: string, template_id: number) => post<{ ok: boolean; template_id: number; item_id: string }>(mail(id, "copy"), { template_id }),
  emailLoad: (id: string, template_id: number) => post<EmailLoadOut>(mail(id, "load"), { template_id }),
  emailLinesFields: (id: string, template_id: number, field: string) =>
    post<{ field: string; columns: LineColumn[] }>(mail(id, "lines-fields"), { template_id, field }),
  emailPreview: (id: string, body: { template_id: number; record_id: number; placements?: Placement[] | null; highlight?: { slot: string; index: number }[] | null }, signal?: AbortSignal) =>
    post<EmailPreviewOut>(mail(id, "preview"), body, signal),
  /** Touch 132: sends the rendered preview to the signed-in person's own address only (server picks the address). */
  emailSendMeTest: (id: string, body: { template_id: number; record_id: number; placements?: Placement[] | null }) =>
    post<{ sent_to: string; subject: string }>(mail(id, "test-send"), body),
  emailSave: (id: string, body: { template_id: number; record_id: number; placements: Placement[] }) =>
    post<{ ok: boolean; previous_body: string } & EmailPreviewOut>(mail(id, "save"), body),
  /** Puts back the body saved before the last save (the server keeps it; no HTML is sent). */
  emailRestore: (id: string, template_id: number) => post<{ ok: boolean }>(mail(id, "restore"), { template_id }),
  emailDelete: (id: string, template_id: number) => post<{ ok: boolean }>(mail(id, "delete"), { template_id }),
};

/** Edit with AI (SPEC 20.1): typed block ops proposed by the AI, checked by the server. */
export type AIBlockOp = { op: "add" | "remove" | "edit" | "move"; slot: string; index?: number; to_slot?: string; to_index?: number | null; block?: Record<string, unknown> };
export type AIEditOut = { ops: AIBlockOp[]; descriptions: string[]; unclear: string | null; choices: string[]; placements: Placement[] };
