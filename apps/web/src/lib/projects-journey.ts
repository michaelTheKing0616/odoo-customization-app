/** Projects journey — chrome only, not the apply/promote engines. */

import type { ProjectDiffOut, SnapshotRow } from "@/lib/api";
import { REVERSIBILITY, SCORE_BARS } from "@/lib/copy-guide";

export const PROJECTS_STAGES = [
  { id: "browse", label: "Browse" },
  { id: "inspect", label: "Inspect" },
  { id: "review", label: "Review" },
  { id: "apply", label: "Apply" },
] as const;

export type ProjectsJourneyId = (typeof PROJECTS_STAGES)[number]["id"];

export type ProjectsJourneyState = {
  id: ProjectsJourneyId;
  failed?: boolean;
  applied?: boolean;
};

export type ProjectsSessionState = "draft" | "applied" | "archived";

export type ProjectsBusy =
  | "create"
  | "diff"
  | "apply"
  | "archive"
  | "delete"
  | "rollback"
  | null;

export type ProjectsBoardFilter = "all" | "draft" | "applied" | "archived";

export type ProjectRow = {
  id: string;
  name: string;
  template_id: string | null;
  status: string;
  lifecycle_status?: string;
  spec_json: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProjectSpecSummary = {
  models: number;
  fields: number;
  views: number;
  menus: number;
  access: number;
};

export type ProjectDiffStats = {
  createModels: number;
  createFields: number;
  existingModels: number;
  existingFields: number;
  conflicts: number;
  toCreate: number;
  alreadyLive: number;
};

export type ProjectsHonestyGate = {
  variant: "info" | "warning" | "danger";
  title: string;
  body: string;
  reason: "production" | "observer" | "sandbox" | "staging";
};

export const PROJECT_SNAPSHOT_TYPES = new Set(["model", "field", "view", "applied_project"]);

export const PROJECT_DIFF_FILTERS = [
  { id: "all", label: "All" },
  { id: "conflicts", label: "Conflicts" },
  { id: "create", label: "To create" },
  { id: "existing", label: "Already live" },
] as const;

export type ProjectDiffFilter = (typeof PROJECT_DIFF_FILTERS)[number]["id"];

export function isProjectArchived(project: Pick<ProjectRow, "lifecycle_status"> | null | undefined): boolean {
  return (project?.lifecycle_status ?? "active") === "archived";
}

export function isProjectApplied(project: Pick<ProjectRow, "status"> | null | undefined): boolean {
  return (project?.status ?? "draft") === "applied";
}

export function projectSpecSummary(spec: Record<string, unknown> | null | undefined): ProjectSpecSummary {
  const models = Array.isArray(spec?.models) ? spec.models : [];
  const fields = models.reduce((n, raw) => {
    if (!raw || typeof raw !== "object") return n;
    const list = (raw as { fields?: unknown }).fields;
    return n + (Array.isArray(list) ? list.length : 0);
  }, 0);
  return {
    models: models.length,
    fields,
    views: Array.isArray(spec?.views) ? spec.views.length : 0,
    menus: Array.isArray(spec?.menus) ? spec.menus.length : 0,
    access: Array.isArray(spec?.access_rules) ? spec.access_rules.length : 0,
  };
}

export function specModelNames(spec: Record<string, unknown> | null | undefined): string[] {
  if (!Array.isArray(spec?.models)) return [];
  return spec.models
    .map((raw) => {
      if (!raw || typeof raw !== "object") return "";
      return String((raw as { model?: unknown }).model || "").trim();
    })
    .filter(Boolean);
}

export function firstCustomModel(spec: Record<string, unknown> | null | undefined): string | null {
  const names = specModelNames(spec);
  return names.find((name) => name.startsWith("x_")) ?? names[0] ?? null;
}

export function hasProjectSpec(spec: Record<string, unknown> | null | undefined): boolean {
  const summary = projectSpecSummary(spec);
  return summary.models > 0 || summary.views > 0 || summary.menus > 0;
}

export function isComponentSpec(spec: Record<string, unknown> | null | undefined): boolean {
  if (!spec) return false;
  if (spec._component) return true;
  const grain = typeof spec.grain === "string" ? spec.grain : "";
  return Boolean(grain && grain !== "full_app");
}

export function projectsJourneyFromState(opts: {
  selected?: boolean;
  hasDiff?: boolean;
  applied?: boolean;
  busy?: ProjectsBusy;
  failed?: boolean;
}): ProjectsJourneyState {
  const failed = Boolean(opts.failed);
  if (opts.busy === "apply") return { id: "apply", failed, applied: Boolean(opts.applied) };
  if (opts.applied && opts.selected) return { id: "apply", applied: true, failed };
  if (opts.busy === "diff") return { id: "review", failed };
  if (opts.hasDiff && opts.selected) return { id: "review", failed, applied: Boolean(opts.applied) };
  if (opts.selected) return { id: "inspect", failed, applied: Boolean(opts.applied) };
  return { id: "browse", failed };
}

export function projectsJourneyHint(state: ProjectsJourneyState): string {
  if (state.failed && state.id === "review") {
    return "Review vs live did not finish. Check the connection, then try again. Completeness is not go-live. Promote stays human.";
  }
  if (state.failed && state.id === "apply") {
    return "Apply did not finish. Prefer a sandbox. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
  }
  switch (state.id) {
    case "browse":
      return "Pick a draft or create one. Projects are versioned customization history — not a table dump. Completeness is hygiene, not Certification.";
    case "inspect":
      return "Open the ModuleSpec, then Review vs live before Apply. Snapshot and Rollback live on this board. Completeness ≠ Cert ≠ Autopilot.";
    case "review":
      return "Diff is draft vs live models and fields. Conflicts need a human. Views and menus stay in ModuleSpec Generate UI. Promote stays human.";
    case "apply":
      return "Apply creates missing models and fields. Prefer a sandbox. Snapshot restores definitions when Odoo allows. Promote stays human.";
  }
}

export function projectsHeaderDescription(
  connectionName?: string | null,
  projectName?: string | null,
): string {
  if (connectionName && projectName) {
    return `${connectionName} · ${projectName} — draft, review vs live, then apply`;
  }
  if (connectionName) {
    return `${connectionName} · versioned drafts, diff vs live, snapshot, and rollback`;
  }
  return "Versioned customization history. Draft, review vs live, then apply. Promote stays human.";
}

export function projectsSessionState(project: ProjectRow | null | undefined): ProjectsSessionState {
  if (!project) return "draft";
  if (isProjectArchived(project)) return "archived";
  if (isProjectApplied(project)) return "applied";
  return "draft";
}

export function projectsSessionHint(state: ProjectsSessionState): string {
  switch (state) {
    case "archived":
      return "Archived drafts keep history readable and free an active slot. Un-archive before Apply. Promote stays human.";
    case "applied":
      return "Last Apply wrote models and fields on this connection. Review vs live again, or restore a snapshot when Odoo allows.";
    case "draft":
      return "Nothing writes to Odoo until Apply. Review vs live, then confirm. Completeness is not go-live.";
  }
}

export function sessionSubmitHint(opts: {
  sessionState: ProjectsSessionState;
  hasDiff?: boolean;
  canApply?: boolean;
}): string {
  if (opts.sessionState === "archived") return "Un-archive to Apply. History stays on this board.";
  if (opts.sessionState === "applied") return "Review vs live, or open ModuleSpec to continue.";
  if (opts.hasDiff && opts.canApply) return "Review the diff, then Apply on a sandbox.";
  if (opts.hasDiff) return "Diff is ready. Fix Apply gates before writing Odoo.";
  return "Select a draft, then Review vs live.";
}

export function projectsErrorTitle(message: string | null | undefined): string {
  const text = (message || "").trim();
  if (!text) return "Projects request failed";
  if (/diff/i.test(text)) return "Review vs live failed";
  if (/apply/i.test(text)) return "Apply failed";
  if (/archive/i.test(text)) return "Archive failed";
  if (/rollback|restore/i.test(text)) return "Rollback failed";
  if (/delete/i.test(text)) return "Delete failed";
  if (/create/i.test(text)) return "Create draft failed";
  return "Projects request failed";
}

export function sortProjectBoard(rows: ProjectRow[]): ProjectRow[] {
  return [...rows].sort((a, b) => {
    const archivedA = isProjectArchived(a) ? 1 : 0;
    const archivedB = isProjectArchived(b) ? 1 : 0;
    if (archivedA !== archivedB) return archivedA - archivedB;
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");
  });
}

export function filterProjectBoard(rows: ProjectRow[], filter: ProjectsBoardFilter): ProjectRow[] {
  if (filter === "draft") {
    return rows.filter((row) => !isProjectApplied(row) && !isProjectArchived(row));
  }
  if (filter === "applied") return rows.filter((row) => isProjectApplied(row));
  if (filter === "archived") return rows.filter((row) => isProjectArchived(row));
  return rows;
}

export function projectStatusLabel(project: ProjectRow): string {
  if (isProjectArchived(project)) return "Archived";
  if (isProjectApplied(project)) return "Applied";
  return "Draft";
}

export function projectTemplateLabel(templateId: string | null | undefined): string {
  if (!templateId) return "Blank";
  if (templateId === "library") return "Library";
  return templateId;
}

export function formatProjectWhen(iso?: string | null): string {
  if (!iso) return "No timestamp";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function projectDiffStats(diff: ProjectDiffOut | null | undefined): ProjectDiffStats {
  const createModels = diff?.to_create_models.length ?? 0;
  const createFields = diff?.to_create_fields.length ?? 0;
  const existingModels = diff?.existing_models.length ?? 0;
  const existingFields = diff?.existing_fields.length ?? 0;
  const conflicts = diff?.conflicts.length ?? 0;
  return {
    createModels,
    createFields,
    existingModels,
    existingFields,
    conflicts,
    toCreate: createModels + createFields,
    alreadyLive: existingModels + existingFields,
  };
}

export function projectDiffHeadline(diff: ProjectDiffOut | null | undefined): string {
  if (!diff) return "Review vs live is the change board for this draft.";
  const stats = projectDiffStats(diff);
  if (stats.conflicts > 0) {
    return `${stats.conflicts} conflict${stats.conflicts === 1 ? "" : "s"} need a human before Apply.`;
  }
  if (stats.toCreate > 0) {
    return `${stats.createModels} model${stats.createModels === 1 ? "" : "s"} and ${stats.createFields} field${
      stats.createFields === 1 ? "" : "s"
    } to create. Already-live rows stay as-is.`;
  }
  return "Draft models and fields already exist on live. Apply would skip creates.";
}

export function projectsHonestyGate(opts: {
  writeMode?: string | null;
  localSandboxUrl?: boolean;
}): ProjectsHonestyGate {
  const mode = (opts.writeMode || "standard").toLowerCase();
  if (mode === "production") {
    return {
      variant: "danger",
      title: "Production connection",
      body: "Prefer a sandbox. Apply still needs a human confirm and creates models and fields on this database. Completeness ≠ Cert ≠ Autopilot. Promote stays human.",
      reason: "production",
    };
  }
  if (mode === "observer") {
    return {
      variant: "warning",
      title: "Observer connection",
      body: "Observer is for inspection. Switch write_mode to standard on a sandbox before Apply. Promote stays human.",
      reason: "observer",
    };
  }
  if (opts.localSandboxUrl) {
    return {
      variant: "info",
      title: "Sandbox apply",
      body: "This looks like a local sandbox. Apply creates missing models and fields only. Views, menus, and ACL stay in ModuleSpec Generate UI. Promote stays human.",
      reason: "sandbox",
    };
  }
  return {
    variant: "warning",
    title: "Not a local sandbox",
    body: "Apply writes this connection. Prefer a sandbox first. Snapshot restores views and automations when Odoo allows; created columns are only partially recoverable. Promote stays human.",
    reason: "staging",
  };
}

export function applyRisks(): string[] {
  return [
    "Creates ir.model / ir.model.fields on the live target",
    "v1 Apply does not create views, menus, or ACL from the draft",
    "Dropped columns and created x_ models are only partially recoverable",
    "Prefer a sandbox connection. Promote stays human",
  ];
}

export function applySnapshotNote(): string {
  return "Apply does not fully roll back created columns. Restore views and automations from snapshots when Odoo allows. Dropped columns are only partially recoverable.";
}

export function snapshotsForProject(
  snapshots: SnapshotRow[],
  project: ProjectRow | null | undefined,
): SnapshotRow[] {
  const typed = snapshots.filter((row) => PROJECT_SNAPSHOT_TYPES.has(row.resource_type));
  if (!project) return typed;
  const models = specModelNames(project.spec_json);
  const scoped = typed.filter((row) => {
    if (row.resource_type === "applied_project") {
      return row.resource_key.includes(project.id) || row.label.includes(project.name);
    }
    if (models.length === 0) return true;
    return models.some(
      (model) => row.resource_key.includes(model) || row.label.includes(model),
    );
  });
  return scoped.length ? scoped : typed;
}

export function snapshotReversibilityLabel(reversible: string): string {
  if (reversible === "yes") return REVERSIBILITY.yes;
  if (reversible === "partial") return REVERSIBILITY.partial;
  return REVERSIBILITY.none;
}

export function canRollbackSnapshot(reversible: string): boolean {
  return reversible !== "no" && reversible !== "none";
}

export function honestyLegend(): string[] {
  return [SCORE_BARS.completeness, SCORE_BARS.certification, SCORE_BARS.autopilot];
}

export function glossaryLines(): string[] {
  return [
    "Draft is the saved ModuleSpec on this board — not a live Odoo write.",
    "Apply creates missing models and fields. Generate UI in ModuleSpec writes views and menus.",
    "Promote stays human. Sandbox first. Completeness is not Certification or Autopilot.",
    "Snapshot is a restore point. Rollback restores definitions when Odoo allows; columns are partial.",
  ];
}

export function modulespecHref(connectionId: string, projectId: string): string {
  return `/connections/${connectionId}/modulespec?project=${encodeURIComponent(projectId)}`;
}

export function designerHref(connectionId: string, model?: string | null): string {
  const base = `/connections/${connectionId}/designer`;
  const trimmed = (model || "").trim();
  return trimmed ? `${base}?model=${encodeURIComponent(trimmed)}` : base;
}

export function journalHref(connectionId: string): string {
  return `/connections/${connectionId}/journal`;
}
